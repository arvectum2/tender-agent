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
        "question": "Из каких частей состоит заявка на участие, какие документы реально обязательны именно для этой закупки услуг и в какой форме подаётся заявка? Условные или товарные поля отдели от безусловных требований.",
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
        "question": "Какие ограничения и преимущества установлены: СМП, СОНКО, национальный режим и преференции? Условия освобождения от обеспечения и иные исключения передай как условные, если документ связывает их с требованиями закона.",
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
