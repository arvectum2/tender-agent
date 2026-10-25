# Tender Agent — единственный рабочий интерфейс оператора

**Каноническое правило Owner от 17.10.2026:** уже существует Operator Workspace. Нельзя создавать второй Pilot Wizard, альтернативную Operator Workspace UI или постоянный третий стенд.

- **Единственный UI:** src/modules/tender_operator_agent_demo/assets/operator_workspace.html, operator_workspace.js, operator_workspace.css. Развивать и чинить только их.
- **Основная ссылка:** http://127.0.0.1:18082/pilot/tender-agent/workspace. Это существующий локальный Mac mini Pilot API. Только loopback / имеющиеся авторизованные SSH/Tailscale-туннели и существующая Basic Auth; не открывать публично.
- **Совместимость:** /pilot/tender-agent отдаёт идентичный HTML; /demo/tender-agent/wizard перенаправляет на основной приватный путь.
- **Данные:** существующий EIS intake, original documents, saved runs, citation checks, reports/PDF/DOCX, история, canonical PostgreSQL и ArvectumSSD, без дублей.
- **Старое /demo/tender-agent:** тестовая/demo совместимость, не новый операторский интерфейс.
- **Единственный локальный API runtime:** существующий Compose-проект arvectum-local-e2e, сервис arvectum-local-e2e-api-1 на 127.0.0.1:18082, прежние db/redis/worker и тома. Контейнер arvectum-apr03b-preview-api на 18083 дублирует UI и должен быть остановлен после проверки обновлённого 18082. Никакие общие тома или каноническую БД не удалять.
- Временные ephemeral QA допустимы только во время тестов, но не как постоянный новый фронтенд.
- Приватный Compose Docker overlay заменяет целиком src, scripts, migrations и помечен SHA; не сохранять устаревший пилотный мастер в собранном image.
- SaaS /saas и отдельный onboarding /pilot/onboarding не оправдывают новый интерфейс анализа закупок.

**Правило продолжения:** перед новым UI-этапом проверять существующие assets, router, Compose, БД, источники и ранее написанные тесты. Повторно использовать текущий код и исправлять его. Новые frontend, UI-route, CSS/JS копии, Docker service, database или постоянные стенды без отдельного решения владельца запрещены. Технический тест не является owner/legal GO, согласованием платёжной операции, подписи или отправки заявки.
