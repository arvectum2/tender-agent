import json

from src.tender_research.rag.llm import LocalChatLlmClient
from src.tender_research.rag.search_types import RagSearchHit


class Response:
    def __init__(self, data):
        self.data = json.dumps(data).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self):
        return self.data


def _hit():
    return RagSearchHit(
        chunk_id="ce05b458-5069-4b62-bbc3-dce35b66b665",
        score=0.8,
        registry_number="32616445795",
        tender_id="t",
        tender_title="Original",
        customer_name=None,
        document_id="doc",
        file_name="spec.docx",
        chunk_index=0,
        preview="Срок 2027",
        text="Срок 2027",
    )


def _run(monkeypatch, answer, finish_reason="stop"):
    from src.tender_research.rag import llm

    monkeypatch.setattr(
        llm.urllib.request,
        "urlopen",
        lambda request, timeout: Response(
            {
                "choices": [
                    {
                        "finish_reason": finish_reason,
                        "message": {"content": answer},
                    }
                ]
            }
        ),
    )
    return LocalChatLlmClient(
        base_url="http://127.0.0.1:8088/v1", model_name="qwen"
    ).generate_answer("Срок?", [_hit()], registry_number="32616445795")


def test_real_mutated_223_fz_uuid_fails_closed(monkeypatch):
    x = _run(monkeypatch, "2027 [ce05b458-5062-4b62-bbc3-dce35b66b665]")
    assert x.answer == ""
    assert "unknown or modified" in x.error
    assert len(x.sources) == 1


def test_original_chunk_uuid_is_accepted(monkeypatch):
    x = _run(monkeypatch, "2027 [ce05b458-5069-4b62-bbc3-dce35b66b665]")
    assert x.error is None


def test_44_fz_missing_source_citation_fails_closed(monkeypatch):
    x = _run(monkeypatch, "Топливо 140 тонн")
    assert x.answer == ""
    assert "no verifiable source" in x.error


def test_token_length_finish_reason_fails_closed_even_with_correct_citation(
    monkeypatch,
):
    x = _run(monkeypatch, "2027 [ce05b458-5069-4b62-bbc3-dce35b66b665]", "length")
    assert x.answer == ""
    assert "truncated" in x.error


def test_opaque_non_uuid_chunk_id_is_accepted(monkeypatch):
    x = _run(monkeypatch, "2027, chunk_id=ce05b458-5069-4b62-bbc3-dce35b66b665")
    assert x.error is None
