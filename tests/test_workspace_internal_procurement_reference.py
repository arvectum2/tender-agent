from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import unittest

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable

from src.modules.deal_registry.models import Deal
from src.modules.event_log.models import DecisionRecord, EventRecord
from src.modules.outcome_intake.models import OutcomeIntakeBinding, OutcomeIntakeRecord, OutcomeIntakeSet
from src.modules.procurement_portfolio.workspace_reference import ReferenceDenied, ReferenceScope, read_internal_procurement
from src.modules.tender_screening.models import TenderScreeningRecord


class InternalProcurementReferenceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        self.addCleanup(self.engine.dispose)
        with self.engine.begin() as connection:
            for model in (Deal, DecisionRecord, EventRecord, TenderScreeningRecord,
                          OutcomeIntakeSet, OutcomeIntakeRecord, OutcomeIntakeBinding):
                connection.execute(CreateTable(model.__table__, include_foreign_key_constraints=[]))
        self.session = Session(self.engine)
        self.addCleanup(self.session.close)
        self.now = datetime(2026, 11, 17, 12, tzinfo=timezone.utc)
        self.scope = ReferenceScope("fixture-binding", "a" * 40, "fixture-database",
            frozenset({"DL-fixture"}), self.now - timedelta(hours=1), self.now + timedelta(days=1))
        for key in ("DL-fixture", "DL-other"):
            self.session.add(Deal(deal_id=key, title="PRIVATE_TITLE", customer_name="PRIVATE_CUSTOMER",
                procurement_number="0123456789012345678", initial_source_type="MANUAL_ENTRY",
                direction_type="SERVICE", domain_type="IT", current_status="POST_SUBMISSION",
                created_at=self.now, updated_at=self.now))
        self.session.commit()

    def read(self, **kw):
        args = {"scope": self.scope, "authorize": lambda: self.scope, "clock": lambda: self.now}
        args.update(kw)
        return read_internal_procurement(self.session, **args)

    def decision(self, ref, value, at, who="HUMAN", actor=None):
        self.session.add(DecisionRecord(deal_id="DL-fixture", decision_id=ref,
            decision_code="PORTFOLIO_BID_DECISION", decided_by_type=who, decided_by_ref=actor,
            rationale="PRIVATE_RATIONALE", payload_json={"decision": value, "private": "PRIVATE_PAYLOAD"},
            created_at=at))
        self.session.commit()

    def test_exact_projection_select_only_without_workflow_inference(self):
        statements = []
        event.listen(self.engine, "before_cursor_execute", lambda c, u, s, p, x, m: statements.append(s))
        result = self.read()
        self.assertEqual(len(result["items"]), 1)
        row = result["items"][0]
        self.assertEqual(row["deal_id"], "DL-fixture")
        self.assertEqual(row["workflow_status"], "POST_SUBMISSION")
        self.assertIsNone(row["recorded_decision"])
        self.assertIsNone(row["submission"])
        self.assertIsNone(row["outcome"])
        self.assertEqual(row["current_legal_status"], "unknown")
        self.assertTrue(all(s.strip().upper().startswith("SELECT") for s in statements))
        self.assertNotIn("PRIVATE_", json.dumps(result))
        self.assertNotIn("DL-other", json.dumps(result))

    def test_explicit_latest_decision_not_owner_authority(self):
        self.decision("older", "GO", self.now - timedelta(minutes=2), actor="PRIVATE_ACTOR")
        self.decision("latest", "NO_GO", self.now - timedelta(minutes=1))
        record = self.read()["items"][0]["recorded_decision"]
        self.assertEqual(record["ref"], "latest")
        self.assertEqual(record["value"], "NO_GO")
        self.assertFalse(record["actor_reference_present"])
        self.assertFalse(record["owner_approval_verified"])
        self.assertNotIn("PRIVATE_", json.dumps(record))

    def test_tied_decisions_unknown(self):
        self.decision("one", "GO", self.now)
        self.decision("two", "NO_GO", self.now)
        self.assertIsNone(self.read()["items"][0]["recorded_decision"])

    def test_foreign_missing_revoked_expired_and_oversize_denied(self):
        missing = replace(self.scope, deal_ids=frozenset({"missing"}))
        for scope in (missing, replace(self.scope, expires_at=self.now),
                      replace(self.scope, deal_ids=frozenset(str(i) for i in range(22)))):
            with self.assertRaises(ReferenceDenied):
                self.read(scope=scope, authorize=lambda: scope)
        with self.assertRaises(ReferenceDenied):
            self.read(authorize=lambda: None)
        calls = iter((self.scope, None))
        with self.assertRaises(ReferenceDenied):
            self.read(authorize=lambda: next(calls))

    def test_submission_and_outcome_are_recorded_evidence_only(self):
        self.session.add(EventRecord(event_id="submission-fixture", deal_id="DL-fixture",
            event_code="submission_execution_submitted", severity="INFO", payload_json={"private": "PRIVATE_PAYLOAD"},
            created_at=self.now))
        # This isolated fixture does not create unrelated tracker tables.
        self.session.execute(OutcomeIntakeSet.__table__.insert().values(
            outcome_intake_set_id="outcome-set-fixture", deal_id="DL-fixture",
            post_submission_tracker_set_id="fixture", outcome_status="RECORDED",
            created_at=self.now, updated_at=self.now))
        self.session.execute(OutcomeIntakeRecord.__table__.insert().values(
            outcome_intake_id="outcome-fixture", outcome_intake_set_id="outcome-set-fixture",
            outcome_code="WON", rationale="PRIVATE_TEXT", effective_at=self.now,
            created_at=self.now, updated_at=self.now))
        self.session.commit()
        row = self.read()["items"][0]
        self.assertEqual(row["submission"]["ref"], "submission-fixture")
        self.assertFalse(row["submission"]["external_submission_verified"])
        self.assertEqual(row["outcome"]["code"], "WON")
        self.assertIsNone(row["outcome"]["artifact_ref"])
        self.assertFalse(row["outcome"]["external_outcome_verified"])
        self.assertNotIn("PRIVATE_", json.dumps(row))

    def test_dirty_session_denied(self):
        deal = self.session.query(Deal).filter_by(deal_id="DL-fixture").one()
        deal.title = "dirty"
        with self.assertRaises(ReferenceDenied):
            self.read()
