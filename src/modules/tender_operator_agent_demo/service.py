import json
from functools import lru_cache
from pathlib import Path

from fastapi.responses import FileResponse

from src.modules.tender_operator_agent_demo.schemas import (
    DemoDetailSection,
    DemoFinalRecommendation,
    DemoRecommendationCode,
    DemoReportAction,
    DemoSafetyNotice,
    DemoStep,
    DemoStepStatus,
    DemoTenderCard,
    TenderOperatorDemoReportResponse,
    TenderOperatorDemoRunResponse,
    TenderOperatorDemoStepsResponse,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
DEMO_DATA_DIR = REPO_ROOT / "demo_data" / "tender_operator_agent"
ARVECTUM_ASSETS_DIR = REPO_ROOT / "arvectum-landing" / "public" / "assets"
LOCAL_ASSETS_DIR = Path(__file__).resolve().parent / "assets"
ASSET_MAP = {
    "logo-horizontal.svg": (ARVECTUM_ASSETS_DIR / "brand" / "logo-horizontal.svg", "image/svg+xml"),
    "arvectum-logo-block.svg": (LOCAL_ASSETS_DIR / "arvectum-logo-block.svg", "image/svg+xml"),
    "pt-sans-regular.ttf": (ARVECTUM_ASSETS_DIR / "fonts" / "PTSans-Regular.ttf", "font/ttf"),
    "pt-sans-bold.ttf": (ARVECTUM_ASSETS_DIR / "fonts" / "PTSans-Bold.ttf", "font/ttf"),
    "jetbrains-mono-regular.ttf": (ARVECTUM_ASSETS_DIR / "fonts" / "JetBrainsMono-Regular.ttf", "font/ttf"),
}


def _load_json(file_name: str) -> dict:
    return json.loads((DEMO_DATA_DIR / file_name).read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _load_bundle() -> dict:
    return {
        "tender_summary": _load_json("tender_summary.json"),
        "requirements": _load_json("requirements.json"),
        "supplier_questions": _load_json("supplier_questions.json"),
        "rfq_draft": _load_json("rfq_draft.json"),
        "quotes_comparison": _load_json("quotes_comparison.json"),
        "economics": _load_json("economics.json"),
        "contract_risks": _load_json("contract_risks.json"),
        "final_recommendation": _load_json("final_recommendation.json"),
        "trace": _load_json("trace.json"),
    }


def _build_tender_card(bundle: dict) -> DemoTenderCard:
    tender = bundle["tender_summary"]
    final_recommendation = bundle["final_recommendation"]
    return DemoTenderCard(
        run_id=tender["run_id"],
        prepared_at=tender["prepared_at"],
        title=tender["title"],
        procedure_type=tender["procedure_type"],
        customer=tender["customer"],
        category=tender["category"],
        procurement_code=tender["procurement_code"],
        submission_deadline=tender["submission_deadline"],
        analysis_status=tender["analysis_status"],
        document_count=len(tender["documents"]),
        requirement_count=len(bundle["requirements"]["requirements"]),
        question_count=len(bundle["supplier_questions"]["questions"]),
        final_recommendation=DemoRecommendationCode(final_recommendation["recommendation"]),
        final_recommendation_label=final_recommendation["label"],
        documents=tender["documents"],
    )


def _build_steps(bundle: dict) -> list[DemoStep]:
    tender = bundle["tender_summary"]
    requirements = bundle["requirements"]
    questions = bundle["supplier_questions"]
    rfq = bundle["rfq_draft"]
    quotes = bundle["quotes_comparison"]
    economics = bundle["economics"]
    risks = bundle["contract_risks"]
    final_recommendation = bundle["final_recommendation"]
    trace = bundle["trace"]["per_step"]

    return [
        DemoStep(
            key="documents",
            order=1,
            title="Документы",
            short_title="Документы",
            status=DemoStepStatus.DONE,
            description="Получение и разбор закупочного пакета в demo mode.",
            agent_action="Агент собрал комплект закупочных документов и выделил разделы, влияющие на анализ.",
            result_summary="4 документа разобраны, критичные поля по срокам и договору извлечены.",
            findings=tender["document_signals"],
            human_review=[
                "Проверить, что в демо-пакете нет пропущенных приложений.",
                "Подтвердить, какие документы считаются юридически значимыми для реального контура.",
            ],
            trace=trace["documents"],
            result_sections=[
                DemoDetailSection(
                    title="Документы в прогоне",
                    kind="table",
                    columns=["Документ", "Роль", "Страниц"],
                    rows=[
                        {"Документ": item["name"], "Роль": item["role"], "Страниц": item["pages"]}
                        for item in tender["documents"]
                    ],
                ),
                DemoDetailSection(title="Выделенные сигналы", kind="bullets", items=tender["document_signals"]),
            ],
        ),
        DemoStep(
            key="requirements",
            order=2,
            title="Требования",
            short_title="Требования",
            status=DemoStepStatus.DONE,
            description="Извлечение технических и коммерческих требований из ТЗ и связанных документов.",
            agent_action="Агент структурировал ключевые требования и связал их с источниками в пакете закупки.",
            result_summary="Найдено 7 требований, включая срок поставки, гарантию и сертификаты.",
            findings=[item["title"] for item in requirements["requirements"]],
            human_review=requirements["manual_review_points"],
            trace=trace["requirements"],
            result_sections=[
                DemoDetailSection(
                    title="Ключевые требования",
                    kind="table",
                    columns=["Требование", "Деталь", "Источник"],
                    rows=[
                        {
                            "Требование": item["title"],
                            "Деталь": item["detail"],
                            "Источник": item["source"],
                        }
                        for item in requirements["requirements"]
                    ],
                )
            ],
        ),
        DemoStep(
            key="questions",
            order=3,
            title="Вопросы",
            short_title="Вопросы",
            status=DemoStepStatus.NEEDS_REVIEW,
            description="Выявление неясностей и подготовка вопросника для поставщиков.",
            agent_action="Агент отметил неоднозначности и собрал набор вопросов для RFQ и ручной проверки оператором.",
            result_summary="Сформирован список из 6 вопросов, но перед внешним использованием нужен human review.",
            findings=questions["ambiguities"],
            human_review=questions["manual_checks"],
            trace=trace["questions"],
            result_sections=[
                DemoDetailSection(title="Неясности", kind="bullets", items=questions["ambiguities"]),
                DemoDetailSection(
                    title="Подготовленные вопросы поставщикам",
                    kind="bullets",
                    items=questions["questions"],
                ),
            ],
        ),
        DemoStep(
            key="rfq",
            order=4,
            title="RFQ",
            short_title="RFQ",
            status=DemoStepStatus.DONE,
            description="Подготовка внутреннего draft RFQ на основе требований и вопросов.",
            agent_action="Агент собрал структуру RFQ для операторской проверки и последующей ручной отправки вне системы.",
            result_summary="Черновик RFQ покрывает технические требования, сертификаты, сроки и условия оплаты.",
            findings=rfq["sections"],
            human_review=rfq["manual_checks"],
            trace=trace["rfq"],
            result_sections=[
                DemoDetailSection(title="Состав RFQ", kind="bullets", items=rfq["sections"]),
                DemoDetailSection(title="Целевые поставщики", kind="bullets", items=rfq["supplier_targets"]),
            ],
        ),
        DemoStep(
            key="quotes",
            order=5,
            title="ТКП",
            short_title="ТКП",
            status=DemoStepStatus.DONE,
            description="Сравнение коммерческих предложений по цене, сроку, гарантии и оплате.",
            agent_action="Агент нормализовал ТКП и свёл их в единый формат для операторского выбора.",
            result_summary="Сопоставлены 3 предложения, выявлен компромисс между ценой, сроком и гарантиями.",
            findings=quotes["highlights"],
            human_review=quotes["manual_checks"],
            trace=trace["quotes"],
            result_sections=[
                DemoDetailSection(
                    title="Сравнение ТКП",
                    kind="table",
                    columns=["Поставщик", "Цена", "Срок", "Гарантия", "Оплата"],
                    rows=[
                        {
                            "Поставщик": item["supplier"],
                            "Цена": item["price"],
                            "Срок": item["lead_time"],
                            "Гарантия": item["warranty"],
                            "Оплата": item["payment_terms"],
                        }
                        for item in quotes["suppliers"]
                    ],
                ),
                DemoDetailSection(title="Ключевые наблюдения", kind="bullets", items=quotes["highlights"]),
            ],
        ),
        DemoStep(
            key="economics",
            order=6,
            title="Экономика",
            short_title="Экономика",
            status=DemoStepStatus.WARNING,
            description="Расчёт базовой экономики сделки с учётом риска и кассового разрыва.",
            agent_action="Агент собрал выручку, себестоимость, логистику и резерв на риск в один economics snapshot.",
            result_summary=economics["result"],
            findings=economics["drivers"],
            human_review=economics["manual_checks"],
            trace=trace["economics"],
            result_sections=[
                DemoDetailSection(
                    title="Экономический срез",
                    kind="table",
                    columns=["Показатель", "Значение"],
                    rows=[
                        {"Показатель": item["label"], "Значение": item["value"]}
                        for item in economics["metrics"]
                    ],
                ),
                DemoDetailSection(title="Что влияет на решение", kind="bullets", items=economics["drivers"]),
            ],
        ),
        DemoStep(
            key="risks",
            order=7,
            title="Риски",
            short_title="Риски",
            status=DemoStepStatus.WARNING,
            description="Оценка контрактных и операционных рисков перед рекомендацией.",
            agent_action="Агент агрегировал риски по срокам, договору, аналогам и финансированию в один понятный блок.",
            result_summary=risks["summary"],
            findings=[item["risk"] for item in risks["risks"]],
            human_review=risks["manual_checks"],
            trace=trace["risks"],
            result_sections=[
                DemoDetailSection(
                    title="Ключевые риски",
                    kind="table",
                    columns=["Риск", "Серьёзность", "Влияние", "Смягчение"],
                    rows=[
                        {
                            "Риск": item["risk"],
                            "Серьёзность": item["severity"],
                            "Влияние": item["impact"],
                            "Смягчение": item["mitigation"],
                        }
                        for item in risks["risks"]
                    ],
                )
            ],
        ),
        DemoStep(
            key="decision",
            order=8,
            title="Решение",
            short_title="Решение",
            status=DemoStepStatus.NEEDS_REVIEW,
            description="Формирование рекомендации по участию для человека, а не вместо человека.",
            agent_action="Агент свёл требования, ТКП, экономику и риски в итоговую рекомендацию с ограничениями.",
            result_summary=f"Рекомендация: {final_recommendation['label']}.",
            findings=final_recommendation["rationale"],
            human_review=final_recommendation["manual_checks"],
            trace=trace["decision"],
            result_sections=[
                DemoDetailSection(title="Причины", kind="bullets", items=final_recommendation["rationale"]),
                DemoDetailSection(title="Открытые вопросы", kind="bullets", items=final_recommendation["open_questions"]),
            ],
        ),
    ]


def _build_final_recommendation(bundle: dict) -> DemoFinalRecommendation:
    final_recommendation = bundle["final_recommendation"]
    return DemoFinalRecommendation(
        recommendation=DemoRecommendationCode(final_recommendation["recommendation"]),
        label=final_recommendation["label"],
        rationale=final_recommendation["rationale"],
        key_requirements=final_recommendation["key_requirements"],
        open_questions=final_recommendation["open_questions"],
        risks=final_recommendation["risks"],
        economics=final_recommendation["economics"],
        manual_checks=final_recommendation["manual_checks"],
        trace=bundle["trace"]["overall_explanation"],
    )


def _build_safety_notice(bundle: dict) -> DemoSafetyNotice:
    return DemoSafetyNotice(
        restrictions=[
            "no external actions",
            "no platform submission",
            "no email sending",
            "no digital signature",
            "human approval required",
            "synthetic demo data only",
        ],
        message=bundle["trace"]["human_control_note"],
    )


def get_tender_operator_demo_run() -> TenderOperatorDemoRunResponse:
    bundle = _load_bundle()
    tender_card = _build_tender_card(bundle)
    steps = _build_steps(bundle)
    return TenderOperatorDemoRunResponse(
        subtitle="Как ИИ-агент разбирает закупку и готовит решение для человека",
        tender=tender_card,
        steps=steps,
        final_recommendation=_build_final_recommendation(bundle),
        trace_summary=bundle["trace"]["decision_factors"],
        safety=_build_safety_notice(bundle),
        report_actions=[
            DemoReportAction(label="Открыть отчёт", href="/demo/tender-agent/report"),
            DemoReportAction(label="Скачать JSON", href="/api/demo/tender-agent/report/download"),
        ],
    )


def get_tender_operator_demo_steps() -> TenderOperatorDemoStepsResponse:
    run = get_tender_operator_demo_run()
    return TenderOperatorDemoStepsResponse(run_id=run.tender.run_id, steps=run.steps)


def _build_report_sections(run: TenderOperatorDemoRunResponse) -> list[DemoDetailSection]:
    return [
        DemoDetailSection(title="Ключевые требования", kind="bullets", items=run.final_recommendation.key_requirements),
        DemoDetailSection(title="Открытые вопросы", kind="bullets", items=run.final_recommendation.open_questions),
        DemoDetailSection(title="Риски", kind="bullets", items=run.final_recommendation.risks),
        DemoDetailSection(title="Экономика", kind="bullets", items=run.final_recommendation.economics),
        DemoDetailSection(title="Ручные проверки", kind="bullets", items=run.final_recommendation.manual_checks),
    ]


def get_tender_operator_demo_report() -> TenderOperatorDemoReportResponse:
    run = get_tender_operator_demo_run()
    report_markdown = (
        "# Отчёт демо тендерного агента\n\n"
        f"- Run ID: {run.tender.run_id}\n"
        f"- Закупка: {run.tender.title}\n"
        f"- Заказчик: {run.tender.customer}\n"
        f"- Код рекомендации: {run.final_recommendation.recommendation.value}\n"
        f"- Рекомендация: {run.final_recommendation.label}\n\n"
        "## Краткий вывод\n"
        + "\n".join(f"- {item}" for item in run.final_recommendation.rationale)
        + "\n\n## Ручные проверки\n"
        + "\n".join(f"- {item}" for item in run.final_recommendation.manual_checks)
        + "\n"
    )
    return TenderOperatorDemoReportResponse(
        run_id=run.tender.run_id,
        report_title="Отчёт демо тендерного агента",
        generated_at=run.tender.prepared_at,
        recommendation=run.final_recommendation.recommendation,
        recommendation_label=run.final_recommendation.label,
        executive_summary=run.final_recommendation.rationale,
        manual_checks=run.final_recommendation.manual_checks,
        sections=_build_report_sections(run),
        report_markdown=report_markdown,
    )


def get_tender_operator_demo_report_download() -> tuple[str, bytes]:
    report = get_tender_operator_demo_report()
    payload = report.model_dump_json(indent=2).encode("utf-8")
    return "tender_operator_agent_demo_report.json", payload


def get_demo_asset_response(asset_name: str) -> FileResponse:
    asset_path, media_type = ASSET_MAP[asset_name]
    return FileResponse(asset_path, media_type=media_type, filename=asset_path.name)


def _base_page_css() -> str:
    return """
    @font-face {
      font-family: 'PT Sans';
      src: url('/demo/tender-agent/assets/pt-sans-regular.ttf') format('truetype');
      font-weight: 400;
      font-style: normal;
    }
    @font-face {
      font-family: 'PT Sans';
      src: url('/demo/tender-agent/assets/pt-sans-bold.ttf') format('truetype');
      font-weight: 700;
      font-style: normal;
    }
    @font-face {
      font-family: 'JetBrains Mono';
      src: url('/demo/tender-agent/assets/jetbrains-mono-regular.ttf') format('truetype');
      font-weight: 400;
      font-style: normal;
    }
    :root {
      --mint-primary: #00c8a0;
      --mint-light: #78fae6;
      --deep-navy: #001432;
      --graphite: #283246;
      --soft-gray: #c8d2dc;
      --white: #ffffff;
      --line: rgba(200, 210, 220, 0.18);
      --panel: rgba(255, 255, 255, 0.06);
      --panel-strong: rgba(255, 255, 255, 0.1);
      --warning: #ffb454;
      --review: #8bd8ff;
      --danger: #ff7f87;
      --shadow: 0 28px 80px rgba(0, 20, 50, 0.28);
      --radius-lg: 28px;
      --radius-md: 20px;
      --radius-sm: 14px;
    }
    * { box-sizing: border-box; }
    html, body { margin: 0; min-height: 100%; }
    body {
      font-family: 'PT Sans', sans-serif;
      color: var(--white);
      background:
        radial-gradient(circle at top left, rgba(0, 200, 160, 0.18), transparent 32%),
        radial-gradient(circle at 85% 8%, rgba(120, 250, 230, 0.16), transparent 24%),
        linear-gradient(180deg, #03142f 0%, #001432 48%, #081c34 100%);
    }
    body::before {
      content: '';
      position: fixed;
      inset: 0;
      background-image:
        linear-gradient(rgba(255, 255, 255, 0.02) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255, 255, 255, 0.02) 1px, transparent 1px);
      background-size: 48px 48px;
      pointer-events: none;
      mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.4), transparent 92%);
    }
    a { color: inherit; }
    .page {
      width: min(1400px, calc(100vw - 48px));
      margin: 0 auto;
      padding: 32px 0 56px;
      position: relative;
      z-index: 1;
    }
    .shell {
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.08), rgba(255, 255, 255, 0.03));
      border: 1px solid var(--line);
      border-radius: 36px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(18px);
      overflow: hidden;
    }
    .header {
      display: flex;
      justify-content: space-between;
      gap: 24px;
      align-items: flex-start;
      padding: 32px 32px 20px;
      border-bottom: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(120, 250, 230, 0.06), rgba(255, 255, 255, 0.02));
    }
    .brand {
      display: flex;
      gap: 18px;
      align-items: center;
    }
    .brand img {
      width: 160px;
      max-width: 34vw;
      filter: brightness(1.08);
    }
    .eyebrow, .mono, .status-chip, .badge, .legend-item code {
      font-family: 'JetBrains Mono', monospace;
    }
    .eyebrow {
      color: var(--mint-light);
      font-size: 12px;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      margin-bottom: 8px;
    }
    h1 {
      margin: 0 0 8px;
      font-size: clamp(32px, 4vw, 56px);
      line-height: 0.95;
      max-width: 11ch;
    }
    .subtitle {
      margin: 0;
      max-width: 680px;
      color: rgba(255, 255, 255, 0.78);
      font-size: 18px;
      line-height: 1.45;
    }
    .header-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      justify-content: flex-end;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 10px 14px;
      border-radius: 999px;
      background: rgba(0, 200, 160, 0.12);
      border: 1px solid rgba(120, 250, 230, 0.32);
      color: var(--mint-light);
      font-size: 12px;
      letter-spacing: 0.04em;
    }
    .content {
      display: grid;
      grid-template-columns: minmax(320px, 0.85fr) minmax(0, 1.35fr);
      gap: 20px;
      padding: 20px;
    }
    .stack {
      display: grid;
      gap: 20px;
      align-content: start;
    }
    .card {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: var(--radius-lg);
      padding: 22px;
    }
    .card h2, .card h3 {
      margin: 0 0 14px;
      font-size: 22px;
    }
    .card p {
      margin: 0;
      color: rgba(255, 255, 255, 0.78);
      line-height: 1.5;
    }
    .card-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px 18px;
    }
    .metric {
      padding: 14px 16px;
      border-radius: var(--radius-sm);
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid rgba(255, 255, 255, 0.08);
    }
    .metric-label {
      display: block;
      color: rgba(255, 255, 255, 0.62);
      font-size: 12px;
      margin-bottom: 4px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }
    .metric-value {
      display: block;
      font-size: 17px;
      line-height: 1.35;
    }
    .document-list, .bullet-list, .action-list {
      list-style: none;
      margin: 0;
      padding: 0;
      display: grid;
      gap: 10px;
    }
    .document-item, .bullet-item, .action-item {
      padding: 12px 14px;
      border-radius: var(--radius-sm);
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid rgba(255, 255, 255, 0.07);
    }
    .document-meta {
      color: rgba(255, 255, 255, 0.56);
      font-size: 13px;
      margin-top: 4px;
    }
    .legend {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }
    .legend-item {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 10px 12px;
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid rgba(255, 255, 255, 0.07);
      border-radius: 999px;
      color: rgba(255, 255, 255, 0.74);
      font-size: 13px;
    }
    .status-dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: var(--soft-gray);
      box-shadow: 0 0 0 6px rgba(255, 255, 255, 0.04);
    }
    .status-done { background: var(--mint-primary); }
    .status-needs_review { background: var(--review); }
    .status-warning { background: var(--warning); }
    .status-blocked { background: var(--danger); }
    .status-pending { background: var(--soft-gray); }
    .status-running { background: var(--mint-light); }
    .pipeline {
      display: grid;
      gap: 14px;
    }
    .pipeline-header {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: center;
      margin-bottom: 6px;
    }
    .pipeline-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
    }
    .step-button {
      appearance: none;
      width: 100%;
      text-align: left;
      border: 1px solid rgba(255, 255, 255, 0.08);
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.06), rgba(255, 255, 255, 0.03));
      color: var(--white);
      border-radius: 18px;
      padding: 16px;
      cursor: pointer;
      transition: transform 180ms ease, border-color 180ms ease, background 180ms ease;
      min-height: 132px;
    }
    .step-button:hover,
    .step-button.active {
      transform: translateY(-2px);
      border-color: rgba(120, 250, 230, 0.44);
      background: linear-gradient(180deg, rgba(0, 200, 160, 0.14), rgba(255, 255, 255, 0.05));
    }
    .step-order {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 20px;
      color: rgba(255, 255, 255, 0.56);
      font-size: 13px;
    }
    .step-title {
      font-size: 21px;
      line-height: 1.1;
      margin: 0 0 8px;
    }
    .step-description {
      color: rgba(255, 255, 255, 0.72);
      font-size: 14px;
      line-height: 1.45;
    }
    .status-chip {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      font-size: 12px;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      color: rgba(255, 255, 255, 0.76);
    }
    .detail-grid {
      display: grid;
      grid-template-columns: 1.05fr 0.95fr;
      gap: 18px;
    }
    .detail-panel {
      display: grid;
      gap: 16px;
      align-content: start;
    }
    .section-card {
      padding: 18px;
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.035);
      border: 1px solid rgba(255, 255, 255, 0.07);
    }
    .section-title {
      margin: 0 0 10px;
      color: var(--mint-light);
      font-size: 14px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .trace-box {
      padding: 18px;
      border-radius: 18px;
      background: rgba(0, 200, 160, 0.08);
      border: 1px solid rgba(120, 250, 230, 0.2);
    }
    .trace-box p {
      font-family: 'JetBrains Mono', monospace;
      font-size: 13px;
      color: rgba(255, 255, 255, 0.86);
      line-height: 1.65;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }
    th, td {
      text-align: left;
      vertical-align: top;
      padding: 10px 10px 10px 0;
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    }
    th {
      color: rgba(255, 255, 255, 0.58);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }
    tr:last-child td { border-bottom: 0; }
    .summary-card {
      background: linear-gradient(180deg, rgba(0, 200, 160, 0.16), rgba(255, 255, 255, 0.05));
      border: 1px solid rgba(120, 250, 230, 0.28);
    }
    .summary-head {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: flex-start;
      margin-bottom: 16px;
    }
    .summary-title {
      margin: 0 0 6px;
      font-size: 28px;
      line-height: 1.05;
    }
    .recommendation-tag {
      padding: 10px 14px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid rgba(255, 255, 255, 0.18);
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      white-space: nowrap;
    }
    .columns-2 {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }
    .action-row {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
    }
    .button, .link-button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
      min-height: 46px;
      padding: 0 18px;
      border-radius: 999px;
      border: 1px solid rgba(120, 250, 230, 0.26);
      background: rgba(0, 200, 160, 0.12);
      color: var(--white);
      text-decoration: none;
      font-family: 'JetBrains Mono', monospace;
      font-size: 13px;
      cursor: pointer;
      transition: transform 180ms ease, background 180ms ease;
    }
    .button:hover, .link-button:hover {
      transform: translateY(-1px);
      background: rgba(0, 200, 160, 0.18);
    }
    .button.secondary, .link-button.secondary {
      background: rgba(255, 255, 255, 0.05);
      border-color: rgba(255, 255, 255, 0.12);
    }
    .button[disabled], .link-button.disabled {
      opacity: 0.45;
      cursor: not-allowed;
      pointer-events: none;
    }
    .footer-note {
      margin-top: 16px;
      color: rgba(255, 255, 255, 0.58);
      font-size: 13px;
      line-height: 1.55;
    }
    .empty {
      color: rgba(255, 255, 255, 0.64);
      text-align: center;
      padding: 40px 18px;
      border: 1px dashed rgba(255, 255, 255, 0.12);
      border-radius: 18px;
    }
    .loading {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      color: rgba(255, 255, 255, 0.74);
    }
    .loading::before {
      content: '';
      width: 12px;
      height: 12px;
      border: 2px solid rgba(120, 250, 230, 0.24);
      border-top-color: var(--mint-primary);
      border-radius: 50%;
      animation: spin 800ms linear infinite;
    }
    @keyframes spin {
      to { transform: rotate(360deg); }
    }
    @media (max-width: 1120px) {
      .content,
      .detail-grid {
        grid-template-columns: 1fr;
      }
      .pipeline-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
    }
    @media (max-width: 720px) {
      .page {
        width: min(100vw - 24px, 1400px);
        padding: 12px 0 32px;
      }
      .shell {
        border-radius: 28px;
      }
      .header {
        padding: 24px 18px 18px;
        flex-direction: column;
      }
      .content {
        padding: 14px;
      }
      .card-grid,
      .columns-2,
      .pipeline-grid {
        grid-template-columns: 1fr;
      }
      .summary-head {
        flex-direction: column;
      }
      h1 {
        max-width: none;
      }
    }
    """


def render_tender_operator_demo_html() -> str:
    return f"""
    <html lang="ru">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Тендерный агент: демонстрация работы</title>
        <style>{_base_page_css()}</style>
      </head>
      <body>
        <div class="page">
          <div class="shell">
            <header class="header">
              <div>
                <div class="brand">
                  <img src="/demo/tender-agent/assets/logo-horizontal.svg" alt="Arvectum" />
                </div>
                <div class="eyebrow">Демо тендерного агента</div>
                <h1>Тендерный агент</h1>
                <p class="subtitle">Как ИИ-агент разбирает закупку и готовит решение для человека</p>
              </div>
              <div class="header-actions">
                <span class="badge">Демо-режим / подтверждение человеком</span>
                <span class="badge">Синтетические данные / без внешних действий</span>
              </div>
            </header>

            <div class="content">
              <aside class="stack">
                <section class="card" id="tender-card">
                  <div class="loading">Загрузка демо-данных</div>
                </section>
                <section class="card">
                  <h2>Статусы шагов</h2>
                  <div class="legend">
                    <span class="legend-item"><span class="status-dot status-done"></span><code>done</code></span>
                    <span class="legend-item"><span class="status-dot status-needs_review"></span><code>needs_review</code></span>
                    <span class="legend-item"><span class="status-dot status-warning"></span><code>warning</code></span>
                    <span class="legend-item"><span class="status-dot status-blocked"></span><code>blocked</code></span>
                    <span class="legend-item"><span class="status-dot status-pending"></span><code>pending</code></span>
                  </div>
                </section>
                <section class="card">
                  <h2>Подтверждение человека</h2>
                  <p id="safety-message">Агент не выполняет внешние действия самостоятельно. Подача заявки, юридически значимые действия, отправка поставщикам и подписание документов выполняются только после подтверждения человеком.</p>
                  <ul class="bullet-list" id="safety-list"></ul>
                </section>
                <section class="card">
                  <h2>Экспорт и отчёт</h2>
                  <div class="action-row" id="report-actions"></div>
                  <p class="footer-note">Если понадобится связать демо с реальным отчётом конкретного design partner, можно заменить synthetic fixtures на локальный подготовленный пакет данных без внешних действий.</p>
                </section>
              </aside>

              <main class="stack">
                <section class="card pipeline">
                  <div class="pipeline-header">
                    <div>
                      <h2>Pipeline агента</h2>
                      <p>Документы → Требования → Вопросы → RFQ → ТКП → Экономика → Риски → Решение</p>
                    </div>
                    <div class="action-row">
                      <button class="button" id="run-demo-button" type="button">Запустить демонстрационный прогон</button>
                      <a class="link-button secondary" href="/demo/tender-agent/report" target="_blank" rel="noreferrer">Открыть demo report</a>
                    </div>
                  </div>
                  <div class="pipeline-grid" id="pipeline-grid"></div>
                </section>

                <section class="card" id="step-detail">
                  <div class="empty">Выберите шаг, чтобы посмотреть, что сделал агент и что должен проверить человек.</div>
                </section>

                <section class="card summary-card" id="final-summary">
                  <div class="loading">Сборка итоговой рекомендации</div>
                </section>
              </main>
            </div>
          </div>
        </div>

        <script>
          const state = {{
            run: null,
            selectedStepKey: null,
            displayStatuses: new Map(),
            isAnimating: false,
          }};

          const statusText = {{
            pending: 'pending',
            running: 'running',
            done: 'done',
            needs_review: 'needs_review',
            warning: 'warning',
            blocked: 'blocked',
          }};

          const sleep = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));

          function renderTenderCard(run) {{
            const tender = run.tender;
            const deadline = tender.submission_deadline
              ? new Date(tender.submission_deadline).toLocaleString('ru-RU')
              : 'Не указано';
            document.getElementById('tender-card').innerHTML = `
              <h2>Карточка закупки</h2>
              <div class="card-grid">
                <div class="metric"><span class="metric-label">Название закупки</span><span class="metric-value">${{tender.title}}</span></div>
                <div class="metric"><span class="metric-label">Тип процедуры</span><span class="metric-value">${{tender.procedure_type}}</span></div>
                <div class="metric"><span class="metric-label">Заказчик</span><span class="metric-value">${{tender.customer}}</span></div>
                <div class="metric"><span class="metric-label">Категория</span><span class="metric-value">${{tender.category}}</span></div>
                <div class="metric"><span class="metric-label">Срок подачи</span><span class="metric-value">${{deadline}}</span></div>
                <div class="metric"><span class="metric-label">Статус анализа</span><span class="metric-value">${{tender.analysis_status}}</span></div>
                <div class="metric"><span class="metric-label">Количество документов</span><span class="metric-value">${{tender.document_count}}</span></div>
                <div class="metric"><span class="metric-label">Количество найденных требований</span><span class="metric-value">${{tender.requirement_count}}</span></div>
                <div class="metric"><span class="metric-label">Количество вопросов</span><span class="metric-value">${{tender.question_count}}</span></div>
                <div class="metric"><span class="metric-label">Итоговая рекомендация</span><span class="metric-value">${{tender.final_recommendation_label}}</span></div>
              </div>
              <div style="height:18px"></div>
              <h3>Документы</h3>
              <ul class="document-list">
                ${{
                  tender.documents.map((item) => `
                    <li class="document-item">
                      <strong>${{item.name}}</strong>
                      <div class="document-meta">${{item.role}} · ${{item.pages}} стр.</div>
                    </li>
                  `).join('')
                }}
              </ul>
            `;
          }}

          function renderSafety(run) {{
            document.getElementById('safety-message').textContent = run.safety.message;
            document.getElementById('safety-list').innerHTML = run.safety.restrictions
              .map((item) => `<li class="bullet-item">${{item}}</li>`)
              .join('');
          }}

          function renderReportActions(run) {{
            document.getElementById('report-actions').innerHTML = run.report_actions
              .map((item) => `<a class="link-button${{item.enabled ? '' : ' disabled'}}" href="${{item.href}}" ${{item.href.includes('/demo/') ? 'target="_blank" rel="noreferrer"' : ''}}>${{item.label}}</a>`)
              .join('');
          }}

          function currentStepStatus(step) {{
            return state.displayStatuses.get(step.key) || 'pending';
          }}

          function renderPipeline() {{
            if (!state.run) {{
              return;
            }}
            document.getElementById('pipeline-grid').innerHTML = state.run.steps.map((step) => {{
              const currentStatus = currentStepStatus(step);
              const activeClass = state.selectedStepKey === step.key ? 'active' : '';
              return `
                <button class="step-button ${{activeClass}}" data-step-key="${{step.key}}" type="button">
                  <div class="step-order">
                    <span>#${{step.order}}</span>
                    <span class="status-chip"><span class="status-dot status-${{currentStatus}}"></span>${{statusText[currentStatus]}}</span>
                  </div>
                  <h3 class="step-title">${{step.title}}</h3>
                  <div class="step-description">${{step.result_summary}}</div>
                </button>
              `;
            }}).join('');
            for (const button of document.querySelectorAll('.step-button')) {{
              button.addEventListener('click', () => {{
                state.selectedStepKey = button.dataset.stepKey;
                renderPipeline();
                renderStepDetail();
              }});
            }}
          }}

          function renderSection(section) {{
            if (section.kind === 'table') {{
              const header = section.columns.map((column) => `<th>${{column}}</th>`).join('');
              const rows = section.rows.map((row) => `
                <tr>${{section.columns.map((column) => `<td>${{row[column] ?? ''}}</td>`).join('')}}</tr>
              `).join('');
              return `
                <div class="section-card">
                  <h3 class="section-title">${{section.title}}</h3>
                  <table>
                    <thead><tr>${{header}}</tr></thead>
                    <tbody>${{rows}}</tbody>
                  </table>
                </div>
              `;
            }}
            return `
              <div class="section-card">
                <h3 class="section-title">${{section.title}}</h3>
                <ul class="bullet-list">
                  ${{section.items.map((item) => `<li class="bullet-item">${{item}}</li>`).join('')}}
                </ul>
              </div>
            `;
          }}

          function renderStepDetail() {{
            if (!state.run) {{
              return;
            }}
            const step = state.run.steps.find((item) => item.key === state.selectedStepKey) || state.run.steps[0];
            if (!step) {{
              return;
            }}
            state.selectedStepKey = step.key;
            document.getElementById('step-detail').innerHTML = `
              <div class="detail-grid">
                <div class="detail-panel">
                  <div class="summary-head">
                    <div>
                      <div class="eyebrow">Step #${{step.order}}</div>
                      <h2>${{step.title}}</h2>
                      <p>${{step.description}}</p>
                    </div>
                    <div class="recommendation-tag">
                      <span class="status-dot status-${{currentStepStatus(step)}}"></span>
                      ${{statusText[currentStepStatus(step)]}}
                    </div>
                  </div>
                  <div class="section-card">
                    <h3 class="section-title">Что сделал агент</h3>
                    <p>${{step.agent_action}}</p>
                  </div>
                  <div class="section-card">
                    <h3 class="section-title">Что найдено</h3>
                    <ul class="bullet-list">
                      ${{step.findings.map((item) => `<li class="bullet-item">${{item}}</li>`).join('')}}
                    </ul>
                  </div>
                  <div class="section-card">
                    <h3 class="section-title">Что должен проверить человек</h3>
                    <ul class="bullet-list">
                      ${{step.human_review.map((item) => `<li class="bullet-item">${{item}}</li>`).join('')}}
                    </ul>
                  </div>
                  <div class="trace-box">
                    <h3 class="section-title">Почему агент так решил</h3>
                    <p>${{step.trace}}</p>
                  </div>
                </div>
                <div class="detail-panel">
                  <div class="section-card">
                    <h3 class="section-title">Результат шага</h3>
                    <p>${{step.result_summary}}</p>
                  </div>
                  ${{step.result_sections.map(renderSection).join('')}}
                </div>
              </div>
            `;
          }}

          function renderFinalSummary(run) {{
            document.getElementById('final-summary').innerHTML = `
              <div class="summary-head">
                <div>
                  <div class="eyebrow">Final recommendation</div>
                  <h2 class="summary-title">Рекомендация: ${{run.final_recommendation.label}}</h2>
                  <p>${{run.final_recommendation.trace}}</p>
                </div>
                <div class="recommendation-tag">${{run.final_recommendation.recommendation}}</div>
              </div>
              <div class="columns-2">
                <div class="section-card">
                  <h3 class="section-title">Причины</h3>
                  <ul class="bullet-list">${{run.final_recommendation.rationale.map((item) => `<li class="bullet-item">${{item}}</li>`).join('')}}</ul>
                </div>
                <div class="section-card">
                  <h3 class="section-title">Ключевые требования</h3>
                  <ul class="bullet-list">${{run.final_recommendation.key_requirements.map((item) => `<li class="bullet-item">${{item}}</li>`).join('')}}</ul>
                </div>
                <div class="section-card">
                  <h3 class="section-title">Открытые вопросы</h3>
                  <ul class="bullet-list">${{run.final_recommendation.open_questions.map((item) => `<li class="bullet-item">${{item}}</li>`).join('')}}</ul>
                </div>
                <div class="section-card">
                  <h3 class="section-title">Риски</h3>
                  <ul class="bullet-list">${{run.final_recommendation.risks.map((item) => `<li class="bullet-item">${{item}}</li>`).join('')}}</ul>
                </div>
                <div class="section-card">
                  <h3 class="section-title">Экономика</h3>
                  <ul class="bullet-list">${{run.final_recommendation.economics.map((item) => `<li class="bullet-item">${{item}}</li>`).join('')}}</ul>
                </div>
                <div class="section-card">
                  <h3 class="section-title">Ручные проверки</h3>
                  <ul class="bullet-list">${{run.final_recommendation.manual_checks.map((item) => `<li class="bullet-item">${{item}}</li>`).join('')}}</ul>
                </div>
              </div>
              <div style="height:16px"></div>
              <div class="trace-box">
                <h3 class="section-title">Trace / explainability</h3>
                <ul class="bullet-list">${{run.trace_summary.map((item) => `<li class="bullet-item">${{item}}</li>`).join('')}}</ul>
              </div>
            `;
          }}

          async function fetchRun() {{
            const response = await fetch('/api/demo/tender-agent/run');
            if (!response.ok) {{
              throw new Error('Failed to load demo run');
            }}
            return response.json();
          }}

          async function startReplay() {{
            if (!state.run || state.isAnimating) {{
              return;
            }}
            state.isAnimating = true;
            state.displayStatuses = new Map(state.run.steps.map((step) => [step.key, 'pending']));
            renderPipeline();
            renderStepDetail();
            for (const step of state.run.steps) {{
              state.selectedStepKey = step.key;
              state.displayStatuses.set(step.key, 'running');
              renderPipeline();
              renderStepDetail();
              await sleep(360);
              state.displayStatuses.set(step.key, step.status);
              renderPipeline();
              renderStepDetail();
              await sleep(140);
            }}
            state.isAnimating = false;
          }}

          async function bootstrap() {{
            state.run = await fetchRun();
            state.selectedStepKey = state.run.steps[0]?.key || null;
            state.displayStatuses = new Map(state.run.steps.map((step) => [step.key, step.status]));
            renderTenderCard(state.run);
            renderSafety(state.run);
            renderReportActions(state.run);
            renderPipeline();
            renderStepDetail();
            renderFinalSummary(state.run);
            document.getElementById('run-demo-button').addEventListener('click', startReplay);
          }}

          bootstrap().catch((error) => {{
            document.getElementById('tender-card').innerHTML = `<div class="empty">Не удалось загрузить демо-данные: ${{error.message}}</div>`;
            document.getElementById('step-detail').innerHTML = `<div class="empty">Проверьте, что demo fixtures доступны локально.</div>`;
            document.getElementById('final-summary').innerHTML = `<div class="empty">Итоговая рекомендация недоступна.</div>`;
          }});
        </script>
      </body>
    </html>
    """


def render_tender_operator_demo_report_html() -> str:
    report = get_tender_operator_demo_report()
    sections = "".join(
        (
            f"<div class='section-card'><h3 class='section-title'>{section.title}</h3><ul class='bullet-list'>"
            + "".join(f"<li class='bullet-item'>{item}</li>" for item in section.items)
            + "</ul></div>"
        )
        for section in report.sections
    )
    return f"""
    <html lang="ru">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>{report.report_title}</title>
        <style>{_base_page_css()}</style>
      </head>
      <body>
        <div class="page">
          <div class="shell">
            <header class="header">
              <div>
                <div class="brand">
                  <img src="/demo/tender-agent/assets/logo-horizontal.svg" alt="Arvectum" />
                </div>
                <div class="eyebrow">Демо-отчёт</div>
                <h1 style="max-width:none">Отчёт тендерного агента</h1>
                <p class="subtitle">Синтетический отчёт для локальной демонстрации controlled tender workflow.</p>
              </div>
              <div class="header-actions">
                <a class="link-button" href="/demo/tender-agent">Назад к демо</a>
                <a class="link-button secondary" href="/api/demo/tender-agent/report/download">Скачать JSON</a>
              </div>
            </header>
            <div class="content" style="grid-template-columns:1fr">
              <section class="card summary-card">
                <div class="summary-head">
                  <div>
                    <div class="eyebrow">Run ID {report.run_id}</div>
                    <h2 class="summary-title">Рекомендация: {report.recommendation_label}</h2>
                    <p>Этот отчёт основан на synthetic fixtures и предназначен только для демонстрации internal operator console.</p>
                  </div>
                  <div class="recommendation-tag">{report.recommendation.value}</div>
                </div>
                <div class="columns-2">
                  <div class="section-card">
                    <h3 class="section-title">Краткий вывод</h3>
                    <ul class="bullet-list">
                      {"".join(f"<li class='bullet-item'>{item}</li>" for item in report.executive_summary)}
                    </ul>
                  </div>
                  <div class="section-card">
                    <h3 class="section-title">Ручные проверки</h3>
                    <ul class="bullet-list">
                      {"".join(f"<li class='bullet-item'>{item}</li>" for item in report.manual_checks)}
                    </ul>
                  </div>
                </div>
                <div style="height:16px"></div>
                <div class="columns-2">{sections}</div>
              </section>
            </div>
          </div>
        </div>
      </body>
    </html>
    """
