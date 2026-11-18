"""Fail-closed checks for the Mac mini SSD backend identity verifier."""
import json
import plistlib

from scripts.runtime import verify_macmini_backend as verify


class _HealthyResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


class _Opener:
    def open(self, *_args, **_kwargs):
        return _HealthyResponse()


def _setup(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    (tmp_path / "backend.env").write_text("SAFE_TEST=1\n")
    (tmp_path / "backend.env").chmod(0o600)
    (tmp_path / "backend.plist").write_bytes(
        plistlib.dumps({"ProgramArguments": ["/opt/homebrew/bin/node", verify.LAUNCHER]})
    )
    marker = tmp_path / "active.json"
    marker.write_text(
        json.dumps({"commit": "abcd1234", "backend_pid": 42, "source": str(root)})
    )
    monkeypatch.setattr(verify, "ROOT", root)
    monkeypatch.setattr(verify, "CONFIG", tmp_path / "backend.env")
    monkeypatch.setattr(verify, "PLIST", tmp_path / "backend.plist")
    monkeypatch.setattr(verify, "RUNTIME", marker)
    monkeypatch.setattr(verify.urllib.request, "build_opener", lambda *_: _Opener())

    def fake_run(*args):
        if args[0] == "git":
            if "branch" in args:
                return 0, "main"
            if "rev-parse" in args:
                return 0, "abcd1234"
            if "status" in args:
                return 0, ""
        if args[0] == "gh":
            return 0, "abcd1234"
        if args[0] == "launchctl":
            return 0, "state = running"
        if args[0] == "lsof" and "-iTCP:8001" in args:
            return 0, "42"
        if args[0] == "lsof":
            return 0, "p42\nfcwd\nn" + str(root)
        return 1, ""

    monkeypatch.setattr(verify, "run", fake_run)
    return marker


def test_complete_source_identity_is_healthy(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    result = verify.check()
    assert result["status"] == "OK"
    assert all(result["checks"].values())


def test_live_process_commit_mismatch_fails_closed(tmp_path, monkeypatch):
    marker = _setup(tmp_path, monkeypatch)
    marker.write_text(json.dumps({"commit": "old1234", "backend_pid": 42}))
    result = verify.check()
    assert result["status"] == "DRIFT_OR_DEGRADED"
    assert result["checks"]["active_backend_commit_matches_main"] is False


def test_git_status_failure_not_treated_as_clean(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    previous = verify.run

    def fake_run(*args):
        if args[0] == "git" and "status" in args:
            return 1, ""
        return previous(*args)

    monkeypatch.setattr(verify, "run", fake_run)
    result = verify.check()
    assert result["status"] == "DRIFT_OR_DEGRADED"
    assert result["checks"]["local_main_clean"] is False


def _admission_fixture(tmp_path, monkeypatch):
    import hashlib
    from datetime import UTC, datetime, timedelta

    base=tmp_path/'admission';base.mkdir()
    now=datetime(2026,11,18,tzinfo=UTC)
    end=(now+timedelta(days=1)).isoformat()
    release='a'*40
    ids=[f'DL-test{i}' for i in range(12)]
    m={'schema':'arvectum.tender.internal-procurement-access/1','draft_blob':'9c0f7caa552613ab598d9de05b819524a74e8c73',
       'source_release':release,'database_binding':'b'*64,'binding_id':'fixture','deal_ids':ids,
       'starts_at':(now-timedelta(days=1)).isoformat(),'expires_at':end,'token_sha256':'c'*64}
    o={**m,'schema':'arvectum.company.wsf07b.owner-admission-decision/1','organization':'organization/arvectum-company',
       'source_product':'Tender Agent / Procurement Portfolio','status':'approved-exact-set-pending-product-and-workspace-activation',
       'owner_approval_reference':'fixture-approval','excluded_count':9}
    def write(name,d):
        p=base/name;p.write_text(json.dumps(d));p.chmod(0o600);return hashlib.sha256(p.read_bytes()).hexdigest()
    pin=write('source-access.json',m);write('owner-admission.json',o)
    a={'status':'source-and-workspace-read-verified','source_manifest_sha256':pin,'source_release':release,
       'owner_approval_reference':'fixture-approval','expiry':end,'admitted_count':12,'excluded_count':9}
    write('activation-evidence.json',a)
    launcher=tmp_path/'launcher';launcher.write_text(f'export ARVECTUM_WORKSPACE_PROCUREMENT_MANIFEST="{base}/source-access.json"\nexport ARVECTUM_WORKSPACE_PROCUREMENT_MANIFEST_SHA256="{pin}"\nexport ARVECTUM_WORKSPACE_PROCUREMENT_SOURCE_RELEASE="$SHA"\n')
    class Clock:
        fromisoformat=staticmethod(datetime.fromisoformat)
        @staticmethod
        def now(_):return now
    monkeypatch.setattr(verify,'datetime',Clock)
    monkeypatch.setattr(verify,'ADMISSION',base)
    monkeypatch.setattr(verify,'RELEASE_LAUNCHER',str(launcher))
    monkeypatch.setattr(verify,'anonymous_reference_status',lambda:403)
    return release,base,launcher,m,o,a,write


def test_current_admission_exact_receipt(tmp_path, monkeypatch):
    release,*_rest=_admission_fixture(tmp_path,monkeypatch)
    assert verify.workspace_state_matches({'workspace_admitted':True},release)
    assert not verify.workspace_state_matches({'workspace_admitted':False},release)
    assert not verify.workspace_state_matches({'workspace_admitted':True},'0'*40)


def test_tampered_receipts_and_denial(tmp_path, monkeypatch):
    release,base,launcher,m,o,a,write=_admission_fixture(tmp_path,monkeypatch)
    marker={'workspace_admitted':True}
    o['deal_ids']=['DL-other']+o['deal_ids'][1:];write('owner-admission.json',o)
    assert not verify.workspace_state_matches(marker,release)
    o['deal_ids']=m['deal_ids'];write('owner-admission.json',o)
    monkeypatch.setattr(verify,'anonymous_reference_status',lambda:200)
    assert not verify.workspace_state_matches(marker,release)
    monkeypatch.setattr(verify,'anonymous_reference_status',lambda:403)
    (base/'source-access.json').chmod(0o644)
    assert not verify.workspace_state_matches(marker,release)
    assert launcher.exists() and a['admitted_count']==12


def test_inactive_requires_no_exports(tmp_path, monkeypatch):
    release,_,launcher,*_rest=_admission_fixture(tmp_path,monkeypatch)
    monkeypatch.setattr(verify,'anonymous_reference_status',lambda:503)
    assert not verify.workspace_state_matches({'workspace_admitted':False},release)
    launcher.write_text('# inactive')
    assert verify.workspace_state_matches({'workspace_admitted':False},release)
