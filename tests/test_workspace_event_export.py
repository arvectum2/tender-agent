from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from dataclasses import replace
import unittest
from sqlalchemy import create_engine,event,select
from sqlalchemy.orm import Session
from src.modules.integration_outbox.models import IntegrationOutboxEvent
from src.modules.integration_outbox.service import stable_event_key
from src.modules.integration_outbox.workspace_export import ExportScope,ExportDenied,project_event_window

class WorkspaceExportTests(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine("sqlite://")
        self.addCleanup(self.engine.dispose)
        IntegrationOutboxEvent.__table__.create(self.engine)
        self.s=Session(self.engine);self.addCleanup(self.s.close)
        self.now=datetime(2026,11,17,10,tzinfo=timezone.utc)
        self.scope=ExportScope("tenant","customer","owner","token",frozenset({"project"}),
            self.now-timedelta(days=1),self.now+timedelta(days=1))
        self.member=SimpleNamespace(tenant_id="tenant",customer_id="customer",member_id="owner",token_id="token",role="owner")
    def seed(self,run="run",tenant="customer",project="project",kind="analysis_completed",extra=None,at=None):
        aggregate_type,aggregate=("analysis_run",run) if kind=="analysis_completed" else ("procurement_case","case")
        ts=at or self.now-timedelta(minutes=30)
        key=stable_event_key(kind,aggregate_type,aggregate,run)
        common={"event_type":kind,"event_key":key,"aggregate_type":aggregate_type,"aggregate_id":aggregate,"tenant_id":tenant}
        data={"project_id":project,"case_id":"case","status":"completed"} if kind=="analysis_completed" else {"project_id":project,"run_id":run,"reason":"analysis_completed_operator_review"}
        data.update(extra or {})
        self.s.add(IntegrationOutboxEvent(**common,created_at=ts,envelope={"schema_version":"integration-event-v1",**common,"occurred_at":(ts-timedelta(seconds=1)).isoformat(),"data":data}))
        self.s.commit()
    def export(self,**kw):
        return project_event_window(self.s,**{"scope":self.scope,"authorize":lambda:self.member,
            "since":self.now-timedelta(hours=1),"until":self.now,"now":self.now,**kw})
    def test_exact_scope_no_foreign_unscoped_or_other_project(self):
        self.seed();self.seed(kind="review_required")
        self.seed("foreign",tenant="customer2");self.seed("other-project",project="other");self.seed("unscoped",tenant=None)
        seen=[]
        def monitor(conn,cursor,statement,params,context,executemany):seen.append(statement)
        event.listen(self.engine,"before_cursor_execute",monitor)
        d=self.export()
        self.assertEqual(len(d["rows"]),2)
        self.assertEqual({r["tenant_id"] for r in d["rows"]},{"customer"})
        self.assertEqual(d["coverage"],"partial")
        self.assertTrue(all(q.lstrip().upper().startswith("SELECT") for q in seen))
        self.assertEqual(len(seen),1)
    def test_missing_scope_wrong_principal_and_expiry(self):
        for scope in (None,replace(self.scope,token_id="different"),replace(self.scope,expires_at=self.now)):
            with self.assertRaises(ExportDenied):self.export(scope=scope)
        self.member.role="viewer"
        with self.assertRaises(ExportDenied):self.export()
    def test_revocation_during_read(self):
        self.seed();calls=[]
        def auth():
            calls.append(1)
            if len(calls)>1:raise ExportDenied("revoked")
            return self.member
        with self.assertRaises(ExportDenied):self.export(authorize=auth)
    def test_overflow_discards_whole_response(self):
        for i in range(101):self.seed(str(i))
        d=self.export();self.assertEqual(d["state"],"overflow");self.assertEqual(d["rows"],[])
    def test_malformed_extra_payload_and_unknown_window(self):
        self.seed(extra={"private":"do not return"})
        with self.assertRaises(ExportDenied):self.export()
        with self.assertRaises(ExportDenied):self.export(since=self.now-timedelta(days=2))
        with self.assertRaises(ExportDenied):self.export(until=self.now+timedelta(seconds=1))
    def test_half_open_window_and_dirty_session(self):
        self.seed("left",at=self.now-timedelta(hours=1));self.seed("right",at=self.now)
        self.assertEqual([r["aggregate_id"] for r in self.export()["rows"]],["left"])
        r=self.s.scalar(select(IntegrationOutboxEvent));r.aggregate_id="changed"
        with self.assertRaises(ExportDenied):self.export()

    def test_export_is_not_mounted_as_an_api_route(self):
        # This candidate is a source-only projection. It must not become a
        # public endpoint just because it was merged into a review branch.
        from src.main import app
        paths = {getattr(route, "path", None) for route in app.routes}
        self.assertNotIn("/api/saas/workspace/events", paths)
        self.assertNotIn("/api/saas/workspace/events/", paths)

    def test_non_owner_and_empty_project_scope_refused(self):
        self.member.role = "admin"
        with self.assertRaises(ExportDenied):
            self.export()
        self.member.role = "owner"
        with self.assertRaises(ExportDenied):
            self.export(scope=replace(self.scope, project_ids=frozenset()))
