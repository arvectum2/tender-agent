from __future__ import annotations

from dataclasses import dataclass, field

ANALYSIS_MODE_CHOICES = ("fast", "balanced", "detailed")
DEFAULT_ANALYSIS_MODE = "balanced"


@dataclass(frozen=True)
class SourceCitation:
    chunk_id: str
    registry_number: str | None
    tender_title: str
    customer_name: str | None
    document_id: str
    document_file_name: str
    score: float
    quote_preview: str


@dataclass(frozen=True)
class TenderAnalysisSection:
    id: str
    title: str
    question: str
    answer: str
    sources: list[SourceCitation] = field(default_factory=list)
    status: str = "completed"


@dataclass(frozen=True)
class TenderAnalysisResult:
    status: str
    registry_number: str
    sections: list[TenderAnalysisSection]
    sections_count: int
    sources_count: int
    analysis_mode: str = DEFAULT_ANALYSIS_MODE
    report_markdown: str = ""
    report_path: str | None = None
    used_llm: bool = False
    llm_model: str | None = None
    llm_endpoint: str | None = None
    retrieval_provider: str | None = None
    retrieval_model: str | None = None
    retrieval_limit_used: int | None = None
    run_id: str | None = None
    duration_seconds: float | None = None
    timings: dict = field(default_factory=dict)
    per_section_timings: list[dict] = field(default_factory=list)
    llm_calls_count: int = 0
    total_context_chars: int = 0
    max_section_context_chars: int = 0
    avg_section_llm_seconds: float | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    ri223_source_observations: list[dict] = field(default_factory=list)


ANALYSIS_SECTIONS: list[dict[str, str]] = [
    {
        "id": "notice_info",
        "title": "Информация об извещении",
        "question": "Какая информация содержится в извещении о закупке: номер, дата публикации, способ закупки, заказчик?",
    },
    {
        "id": "subject",
        "title": "Предмет закупки",
        "question": "Что является предметом закупки: описание объекта, количество, единицы измерения, начальная максимальная цена контракта?",
    },
    {
        "id": "customer_requirements",
        "title": "Требования к участникам",
        "question": "Какие требования установлены к участникам закупки: квалификационные, ресурсные, лицензии, допуски СРО, соответствие 44-ФЗ?",
    },
    {
        "id": "application_composition",
        "title": "Состав и содержание заявки",
        "question": "Из каких частей состоит заявка на участие, какие документы необходимо предоставить, в какой форме подаётся заявка?",
    },
    {
        "id": "evaluation_criteria",
        "title": "Критерии и порядок оценки",
        "question": "Какие критерии оценки заявок установлены, каков их вес, как рассчитываются баллы?",
    },
    {
        "id": "contract_terms",
        "title": "Условия контракта",
        "question": "Каковы условия исполнения контракта: сроки, порядок оплаты, обеспечение исполнения, ответственность сторон, аванс?",
    },
    {
        "id": "documentation_requirements",
        "title": "Требования к содержанию документов",
        "question": "Какие требования к содержанию и оформлению документов установлены в документации о закупке?",
    },
    {
        "id": "restrictions_benefits",
        "title": "Ограничения и преимущества",
        "question": "Какие ограничения и преимущества установлены: СМП, СОНКО, импортозамещение, национальный режим, преференции?",
    },
    {
        "id": "deadlines",
        "title": "Сроки и ключевые даты",
        "question": "Каковы ключевые даты процедуры: дата окончания подачи заявок, дата рассмотрения, дата подведения итогов?",
    },
    {
        "id": "documents_summary",
        "title": "Состав документации",
        "question": "Какие документы входят в состав документации о закупке, их наименования, объём, наличие разъяснений?",
    },
]


# Source-bound procurement regime is already stored on ProcurementTender.
# 223-FZ never inherits special 44-FZ participant/SME or contract semantics
# merely because its documents are analyzed by the same search/LLM pipeline.
_RI223_QUESTION_OVERRIDES: dict[str, tuple[str, str]] = {
    "notice_info": (
        "Информация об извещении",
        "Какие номер, дата, заказчик, организатор и вид процедуры прямо указаны в документации этой закупки по 223-ФЗ? Какие значения не подтверждены источниками?",
    ),
    "subject": (
        "Предмет закупки",
        "Каков фактический предмет услуг/работ/поставки, объём и начальная максимальная цена договора именно по тексту извещения и технического задания? Есть ли различие между кодом ОКПД2 и фактическими работами?",
    ),
    "customer_requirements": (
        "Требования к участникам",
        "Какие именно требования к участникам, квалификации, персоналу, опыту, СМСП, лицензиям или допускам прямо установлены в документах конкретной закупки по 223-ФЗ? Какие требования остаются неподтверждёнными? Не переносить правила 44-ФЗ.",
    ),
    "contract_terms": (
        "Условия договора",
        "Какие условия проекта договора этой закупки по 223-ФЗ подтверждены источниками: сроки исполнения, цена с НДС или без НДС, оплата, обеспечение и ответственность? Если не найдено, указать неизвестность.",
    ),
    "restrictions_benefits": (
        "Ограничения и особенности участия",
        "Какие ограничения участия и особенности для СМСП либо других категорий прямо установлены в извещении, документации и применимом Положении о закупке заказчика? Не предполагать преимущества и ограничения из 44-ФЗ.",
    ),
}


def analysis_sections_for_regime(law_type: str | None) -> list[dict[str, str]]:
    """Reuse ten established sections, tailoring only genuine RI223 questions.

    This chooses questions for evidence retrieval; it does not decide the
    legal applicability or infer procurement participant eligibility.
    """
    if str(law_type or "").strip().lower() != "223fz":
        return ANALYSIS_SECTIONS
    return [
        {"id": section["id"], "title": _RI223_QUESTION_OVERRIDES[section["id"]][0],
         "question": _RI223_QUESTION_OVERRIDES[section["id"]][1]}
        if section["id"] in _RI223_QUESTION_OVERRIDES else dict(section)
        for section in ANALYSIS_SECTIONS
    ]
