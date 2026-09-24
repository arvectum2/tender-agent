# ARV-022 OCR fallback revalidation — 2026-09-24

Historical ARV-022 asks for OCR/CV fallback for scanned documents, with coordinates, confidence and human review for low-confidence output. This slice only reconciles current repository evidence; it does not adopt or implement an OCR engine.

## Current evidence

Current repository documentation still states that scanned PDFs/images are not OCR-processed in the local RAG/research paths (`docs/tender_research/local_rag_index.md`, `docs/tender_research/macmini_rag_runtime.md`, `docs/tender_research/free_web_research_pipeline.md`). The gap is therefore current and concrete rather than inferred from the July snapshot.

The reuse-first registry already identifies Tesseract OCR as a mature Apache-2.0 reuse candidate and OCRmyPDF as a conditional process-bound candidate with dependency/license review required. The product backlog explicitly classifies ARV-022 as `REUSE` and forbids building a custom OCR engine absent a measured approved gap.

ARV-019 is skipped as already satisfied for continuation purposes: `PROCUREMENT-KANBAN-V1-001` is completed in canonical queue evidence and the branch-hygiene record maps that delivered task to historical ARV-019.

## Reconciliation result

ARV-022 remains partially unsatisfied: text-bearing extraction exists, while scanned-document OCR fallback is absent in the documented runtime paths. No evidence supports inventing OCR technology.

Successor candidate (not admitted): `ARV-022-OCR-ADAPTER-EVAL-001` — evaluate/integrate one existing OCR engine behind a replaceable adapter using synthetic/fixture scanned documents; preserve provenance and low-confidence review signaling; no production rollout, private documents, or custom OCR model/engine.
