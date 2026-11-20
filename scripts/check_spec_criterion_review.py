"""Read-only source criterion and task gate; no evidence authentication or authority."""
import hashlib,json,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DIR=ROOT/"specs/002-master-roadmap-traceability"
PIN="6799bdef88cbe64b4d769f4af4e50f724cc0e312"
SOURCES=json.loads("[{\"path\":\"docs/roadmap/MASTER_ROADMAP.md\",\"sha256\":\"47604d12e74e3d4e73873c0978f2e28cd2690808ea017e48a944a49fa86df4e1\",\"appendix\":\"\\n\\n## Spec Kit — master roadmap traceability candidate (2026-11-20)\\n\\n[Specification](../../specs/002-master-roadmap-traceability/spec.md) · [Plan](../../specs/002-master-roadmap-traceability/plan.md) · [Integration tasks](../../specs/002-master-roadmap-traceability/tasks.md). Existing [Power Quality package](../../specs/001-power-quality-evidence-closure/spec.md) is preserved. No status, authority, executor, or priority changes; master roadmap stays canonical.\\n\"},{\"path\":\"specs/001-power-quality-evidence-closure/spec.md\",\"sha256\":\"f14bf371e06f0435fa4dc800c17ce09398cceeb331c152ec5278bf2e1827512d\",\"appendix\":\"\"},{\"path\":\"specs/001-power-quality-evidence-closure/tasks.md\",\"sha256\":\"42dc465ec920fd7bcaf9c65ce1c64e2121f6034db80ad83c3af1aeed6e372eae\",\"appendix\":\"\"}]")
DEFINITIONS=json.loads("[{\"id\":\"TA-PQ-AC1\",\"source\":\"specs/001-power-quality-evidence-closure/spec.md\",\"first_line\":14,\"last_line\":14,\"task_id\":\"REVIEW-TA-PQ-AC1\",\"native_task_ids\":[\"T004\",\"T005\",\"T006\"]},{\"id\":\"TA-PQ-AC2\",\"source\":\"specs/001-power-quality-evidence-closure/spec.md\",\"first_line\":15,\"last_line\":15,\"task_id\":\"REVIEW-TA-PQ-AC2\",\"native_task_ids\":[\"T004\",\"T005\",\"T006\"]},{\"id\":\"TA-PQ-AC3\",\"source\":\"specs/001-power-quality-evidence-closure/spec.md\",\"first_line\":16,\"last_line\":16,\"task_id\":\"REVIEW-TA-PQ-AC3\",\"native_task_ids\":[\"T004\",\"T005\",\"T006\"]},{\"id\":\"TA-PQ-AC4\",\"source\":\"specs/001-power-quality-evidence-closure/spec.md\",\"first_line\":17,\"last_line\":17,\"task_id\":\"REVIEW-TA-PQ-AC4\",\"native_task_ids\":[\"T005\",\"T006\",\"T014\"]},{\"id\":\"TA-PQ-AC5\",\"source\":\"specs/001-power-quality-evidence-closure/spec.md\",\"first_line\":22,\"last_line\":22,\"task_id\":\"REVIEW-TA-PQ-AC5\",\"native_task_ids\":[\"T008\",\"T009\",\"T010\",\"T014\"]},{\"id\":\"TA-PQ-AC6\",\"source\":\"specs/001-power-quality-evidence-closure/spec.md\",\"first_line\":23,\"last_line\":23,\"task_id\":\"REVIEW-TA-PQ-AC6\",\"native_task_ids\":[\"T009\",\"T010\",\"T011\",\"T014\"]},{\"id\":\"TA-PQ-AC7\",\"source\":\"specs/001-power-quality-evidence-closure/spec.md\",\"first_line\":24,\"last_line\":24,\"task_id\":\"REVIEW-TA-PQ-AC7\",\"native_task_ids\":[\"T013\",\"T014\"]},{\"id\":\"TA-PQ-AC8\",\"source\":\"specs/001-power-quality-evidence-closure/spec.md\",\"first_line\":25,\"last_line\":25,\"task_id\":\"REVIEW-TA-PQ-AC8\",\"native_task_ids\":[\"T011\",\"T012\",\"T014\"]},{\"id\":\"TA-PQ-AC9\",\"source\":\"specs/001-power-quality-evidence-closure/spec.md\",\"first_line\":26,\"last_line\":26,\"task_id\":\"REVIEW-TA-PQ-AC9\",\"native_task_ids\":[\"T013\",\"T014\"]},{\"id\":\"TA-PQ-AC10\",\"source\":\"specs/001-power-quality-evidence-closure/spec.md\",\"first_line\":27,\"last_line\":27,\"task_id\":\"REVIEW-TA-PQ-AC10\",\"native_task_ids\":[\"T014\",\"T017\"]},{\"id\":\"TA-PQ-AC11\",\"source\":\"specs/001-power-quality-evidence-closure/spec.md\",\"first_line\":32,\"last_line\":32,\"task_id\":\"REVIEW-TA-PQ-AC11\",\"native_task_ids\":[\"T015\",\"T016\"]},{\"id\":\"TA-PQ-AC12\",\"source\":\"specs/001-power-quality-evidence-closure/spec.md\",\"first_line\":33,\"last_line\":33,\"task_id\":\"REVIEW-TA-PQ-AC12\",\"native_task_ids\":[\"T015\",\"T016\",\"T017\"]},{\"id\":\"TA-PQ-AC13\",\"source\":\"specs/001-power-quality-evidence-closure/spec.md\",\"first_line\":34,\"last_line\":34,\"task_id\":\"REVIEW-TA-PQ-AC13\",\"native_task_ids\":[\"T015\",\"T016\"]},{\"id\":\"TA-APR05\",\"source\":\"docs/roadmap/MASTER_ROADMAP.md\",\"first_line\":9,\"last_line\":9,\"task_id\":\"REVIEW-TA-APR05\",\"native_task_ids\":[]},{\"id\":\"TA-APR06\",\"source\":\"docs/roadmap/MASTER_ROADMAP.md\",\"first_line\":291,\"last_line\":291,\"task_id\":\"REVIEW-TA-APR06\",\"native_task_ids\":[]},{\"id\":\"TA-PRICE01\",\"source\":\"docs/roadmap/MASTER_ROADMAP.md\",\"first_line\":347,\"last_line\":347,\"task_id\":\"REVIEW-TA-PRICE01\",\"native_task_ids\":[]},{\"id\":\"TA-APR03B\",\"source\":\"docs/roadmap/MASTER_ROADMAP.md\",\"first_line\":121,\"last_line\":121,\"task_id\":\"REVIEW-TA-APR03B\",\"native_task_ids\":[]},{\"id\":\"TA-APR04\",\"source\":\"docs/roadmap/MASTER_ROADMAP.md\",\"first_line\":122,\"last_line\":122,\"task_id\":\"REVIEW-TA-APR04\",\"native_task_ids\":[]},{\"id\":\"TA-SIBUR\",\"source\":\"docs/roadmap/MASTER_ROADMAP.md\",\"first_line\":46,\"last_line\":46,\"task_id\":\"REVIEW-TA-SIBUR\",\"native_task_ids\":[]},{\"id\":\"TA-GEH\",\"source\":\"docs/roadmap/MASTER_ROADMAP.md\",\"first_line\":47,\"last_line\":47,\"task_id\":\"REVIEW-TA-GEH\",\"native_task_ids\":[]},{\"id\":\"TA-AI-TRADING\",\"source\":\"docs/roadmap/MASTER_ROADMAP.md\",\"first_line\":48,\"last_line\":48,\"task_id\":\"REVIEW-TA-AI-TRADING\",\"native_task_ids\":[]},{\"id\":\"TA-TRACK-SHARED\",\"source\":\"docs/roadmap/MASTER_ROADMAP.md\",\"first_line\":50,\"last_line\":56,\"task_id\":\"REVIEW-TA-TRACK-SHARED\",\"native_task_ids\":[]}]")
def validate(data, original, current, board):
    errors=[]
    for s in SOURCES:
        p=s["path"];raw=original[p]
        if hashlib.sha256(raw).hexdigest()!=s["sha256"]:errors.append("baseline hash "+p)
        if current[p]!=raw+s["appendix"].encode("utf-8"):errors.append("unreviewed current source change "+p)
    if data.get("schema")!="arvectum.source-criterion-review/1" or data.get("source_commit")!=PIN or data.get("execution_authorized") is not False or data.get("actual_acceptance_verified") is not False:errors.append("scope/authority")
    rows=data.get("rows",[]); ids=[r["id"] for r in rows]; expected={d["id"]:d for d in DEFINITIONS}
    if set(ids)!=set(expected) or len(ids)!=len(set(ids)):errors.append("criterion coverage")
    tasks=re.findall(r"^- \\[([ xX])\\] (REVIEW-(?:MAX|TA)-[A-Z0-9-]+) \\(((?:MAX|TA)-[A-Z0-9-]+)\\)",board,re.M)
    mapping={(t[1],t[2]):t[0].lower()=="x" for t in tasks}
    if len(tasks)!=len(expected) or len(mapping)!=len(expected):errors.append("task coverage")
    for r in rows:
        d=expected.get(r["id"])
        if not d:continue
        if any(r.get(k)!=v for k,v in d.items()):errors.append("source/task link changed "+r["id"]);continue
        span="\n".join(original[d["source"]].decode().splitlines()[d["first_line"]-1:d["last_line"]])
        if span!=r.get("exact_text"):errors.append("criterion text "+r["id"])
        key=(d["task_id"],d["id"]);state=r.get("state")
        if key not in mapping or mapping[key]!=(state=="verified"):errors.append("task/state "+r["id"])
        if state not in {"open","partial","blocked","verified"} or not str(r.get("next_action","")).strip():errors.append("status "+r["id"])
        if d["native_task_ids"]:
            ids=set(re.findall(r"^- \\[[ xX]\\] (T\\d+[a-z]?)\\b",original["specs/001-power-quality-evidence-closure/tasks.md"].decode(),re.M))
            if not set(d["native_task_ids"])<=ids:errors.append("native task reference "+r["id"])
        if state=="verified":
            ev=r.get("acceptance_evidence",[])
            if not ev or any(e.get("criterion")!=r["id"] or e.get("outcome")!="pass" or not re.fullmatch(r"[0-9a-f]{40}",e.get("source_commit","")) or not re.fullmatch(r"[0-9a-f]{64}",e.get("artifact_sha256","")) or not e.get("receipt_ref") or not e.get("review_ref") for e in ev):errors.append("missing criterion-specific reviewed evidence "+r["id"])
    return errors
def inputs():
    original={s["path"]:subprocess.check_output(["git","-C",str(ROOT),"show",PIN+":"+s["path"]]) for s in SOURCES}
    current={p:(ROOT/p).read_bytes() for p in original}
    return json.loads((DIR/"criteria-review.json").read_text()),original,current,(DIR/"tasks.md").read_text()
if __name__=="__main__":
    errors=validate(*inputs())
    if errors:raise SystemExit("\n".join(errors))
    print("Structural PASS only: original source, criterion and task links; actual acceptance not established.")
