import hashlib
import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.modules.procurement_portfolio.workspace_reference_endpoint import (
    DRAFT,
    PATH,
    SCHEMA,
    install_workspace_reference,
)


class SourceEndpointTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.path = Path(t.name).resolve() / "manifest.json"
        self.now = datetime(2026, 11, 17, 12, tzinfo=UTC)
        self.token = "a" * 64
        self.release = "b" * 40
        self.doc = {
            "schema": SCHEMA, "draft_blob": DRAFT, "binding_id": "fixture-binding",
            "source_release": self.release, "database_binding": "c" * 64,
            "deal_ids": ["DL-fixture"],
            "starts_at": (self.now-timedelta(hours=1)).isoformat(),
            "expires_at": (self.now+timedelta(days=1)).isoformat(),
            "token_sha256": hashlib.sha256(self.token.encode()).hexdigest(),
        }
        self.path.write_text(json.dumps(self.doc))
        self.path.chmod(0o600)
        self.pin = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.calls = 0

    def client(self, enabled=True, reader=None):
        app = FastAPI()
        def read(engine, scope, authorize, clock):
            self.calls += 1
            assert scope.deal_ids == frozenset({"DL-fixture"})
            assert authorize() == scope
            return {"items": [], "fixture": True}
        install_workspace_reference(app, engine=None, path=self.path if enabled else None,
                                    pin=self.pin, release=self.release, reader=reader or read,
                                    clock=lambda:self.now)
        c = TestClient(app, base_url="http://127.0.0.1:8001", client=("127.0.0.1",12345))
        self.addCleanup(c.close)
        return c

    def test_default_and_exact_credential(self):
        self.assertEqual(self.client(False).get(PATH).status_code, 503)
        c = self.client()
        for h in ({}, {"Authorization":"Basic foo"}, {"Authorization":"Bearer "+"b"*64}):
            self.assertEqual(c.get(PATH,headers=h).status_code,403)
        self.assertEqual(self.calls,0)
        r = c.get(PATH,headers={"Authorization":"Bearer "+self.token})
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.headers["cache-control"],"no-store")
        self.assertEqual(self.calls,1)

    def test_reject_browser_proxy_and_query(self):
        c = self.client()
        for extra in ({"Origin":"http://127.0.0.1:8001"},{"X-Forwarded-For":"127.0.0.1"},
                      {"Host":"other"},{"Cookie":"fixture=1"}):
            self.assertEqual(c.get(PATH,headers={"Authorization":"Bearer "+self.token,**extra}).status_code,403)
        self.assertEqual(c.get(PATH+"?deal_id=DL-other",headers={"Authorization":"Bearer "+self.token}).status_code,403)
        self.assertEqual(self.calls,0)

    def test_revoke_or_change_during_read(self):
        def reader(engine, scope, authorize, clock):
            self.path.unlink()
            return {"items":[]}
        c = self.client(reader=reader)
        self.assertEqual(c.get(PATH,headers={"Authorization":"Bearer "+self.token}).status_code,403)

    def test_manifest_mode_and_expiry(self):
        c = self.client()
        self.path.chmod(0o644)
        self.assertEqual(c.get(PATH,headers={"Authorization":"Bearer "+self.token}).status_code,403)
        self.path.chmod(0o600)
        self.now += timedelta(days=2)
        self.assertEqual(c.get(PATH,headers={"Authorization":"Bearer "+self.token}).status_code,403)
        self.assertEqual(self.calls,0)
