# Tender Agent — canonical master roadmap

> Canonical scope/history source for `arvectum2/tender-agent`. The executor queue is only a filtered executable projection and is **not** the complete roadmap.


## Оперативный светофор и следующий исполнимый этап — 2026-10-17

| Продуктовый этап | Состояние | Что именно осталось |
|---|---|---|
| APR-01 / APR-02 | 🟢 Ограниченный scope закрыт | Новые регрессии только по фактическим дефектам |
| APR-03 runtime | 🟡 Код готов, production gate | Российский VPS/TLS/offsite restore/production требует решения Owner; локальный Mac mini не равен production |
| APR-03B операторский кабинет | 🟡 Единый интерфейс :18082 и DEVELOPMENT E2E проверены | Текущая юридическая редакция ЕИС, личная бизнес/браузерная приёмка; нельзя считать архив текущей процедурой |
| APR-04 onboarding | 🟡 Код в main | Owner подтверждает достоверность профиля и пригодность документов ООО |
| APR-05 SaaS | 🟡 Код в main | Реальный контракт, оплата, публичный rollout, бизнес/правовая приёмка не разрешены |
| APR-06/07 quality | 🟡 DEVELOPMENT E2E и источники; независимое качество не принято | Подписанный human-gold, реальный коммерческий KPI, rolling SLO и model promotion недоказаны |
| Procurement LLM | 🟡 Корпус кандидатов, без обучения | Установить права, provenance, независимую разметку и frozen benchmark до обучения |
| **B2B-SOURCE-DISCOVERY / первые два шага** | 🟡 **LLC qualification + повторная оригинальная проверка пяти карточек реализованы** | 17.10 в 21:59 МСК: 5/5 оригиналов HTTP200/публично открыты, текстовые требования совпали; 0/5 подтверждённое право ООО на отклик, цель 15–20 доступных заказов открыта |
| PRICE-01 / ARV-057 | ⚪ Подтверждённый P1 backlog | После source/eligibility gate — детерминированная статистика ставок и независимо заданная себестоимость, не ML-прогноз |

**Очередь без обхода блокировок:** не тратим время на повторную реализацию уже слитого APR-01/02/03B/04/05; внешние и коммерческие gates остаются HUMAN/OWNER. Первый безопасный самостоятельный этап из текущего `TA-ROADMAP-EXEC-20261012` — `TA-B2B-LLC-ELIGIBILITY-20261017`: source-bound пакет юридической/канальной пригодности [отчёт](B2B_LLC_ELIGIBILITY_FIRST_BATCH_2026-10-17.md) и [воспроизводимый снимок](b2b_llc_eligibility_snapshot_2026-10-17.json). Шаг реализован без отправки откликов, оплаты, подписания или изменений runtime; участие ООО по-прежнему UNKNOWN.

**Исполнение по чекбоксам:**
- [x] Часть 1 — первый подтверждённый source-bound пакет пяти B2B-карточек и отдельный юридический фильтр ООО (PR #477).
- [x] Часть 2 — повторный публичный GET 5/5 оригиналов 17.10.2026, сохранены новые SHA/time, прежние даты/статусы и источниковые требования; [операторский отчёт](B2B_LLC_ORIGINAL_SOURCE_REFRESH_2026-10-17.md), [данные](b2b_workspace_llc_live_recheck_2026-10-17.json).
- [ ] Часть 3 — подтвердить применимость обязательной квалификации и реально работающий отклик от **аккаунта ООО**, включая стоимость PRO: 19032 → 19042/19043 → 19006 → 19030.
- [ ] Часть 4 — довести до 15–20 уникальных актуальных корпоративных IT-заказов с подтверждёнными условиями допуска.
- [ ] Отдельно: `PRICE-01` — детерминированная конкурентная ставка/себестоимость, без автоподачи.

**Ограничения:** публичный статус не означает доступ ООО или решение Owner GO, текущий финальный правовой статус и квалификация не подтверждены. PR #477 находится на ревью. Ни одного отклика или платежа не выполнено.


## Оптимизированная Active Product Roadmap — сверено 2026-10-17

Эта секция — **рабочая продуктовая очередь**. Полный ARV/BASE registry ниже остаётся историческим реестром, но открытый checkbox в legacy-реестре **не означает**, что задача автоматически должна быть реализована. Watchdog после исчерпания явной очереди идёт по этой секции; trigger-backlog не исполняется без подтверждённого trigger.

### Сводка интеграции PR — 17.10.2026 (main)

**FREE FIRST IT B2B customer initiative sources COMPLETED PR476 c97e186c8c:** official FL free for-all, Pchel studio100/mo <=USD1000 with stale duplicate risk, CodeLance free unlimited advertised but mixed self-promotion, CONTRACTIS monthly free limited cap unknown, Weblancer only10day trial/HTTP403, ITsNEW free reply unknown. First-party 4 policy page SHA + 3 original actual customer page SHA; 0 authenticated LLC corporate bids, 0 paid purchases. Current source project three candidates Contractis Python AI170k, landing90-150k 34 responses, CodeLance catalog import budget TBD. Official Moscow Portal suppliers free company enrollment with UKЭП is REGULATED offer not private chat. 5074 Mac PASS/285 SKIP+5 focused+GH green. [owner decision](B2B_FREE_FIRST_OUTREACH_CHANNELS_2026-10-17.md) [machine source](b2b_free_first_outreach_sources_2026-10-17.json). Parent 15-20 truly qualified open.



**B2B FREE first proactive client response platform audit (Oct17) IN_PROGRESS:** FL free only for-all/vacancies/contests, Pchel studio 100 free monthly requests <=USD1000 and old mirrored fake-fresh lead risk, CodeLance unlimited free advertised but original live real client catalog imports147 mixed with provider advertisements, CONTRACTIS monthly capped free reply/agent chat with unknown quota and real original Python AI170k, construction landing90-150k (already34 applicants). Weblancer trial10 days and Mac HTTP403; ITsNEW original board but free reply NOT proved. Seven original HTTP200 source SHA, Pchel intermittent fetch marked unavailable rather than invented source; zero actual authenticated LLC first contact GO. [Owner ranking](B2B_FREE_FIRST_OUTREACH_CHANNELS_2026-10-17.md) and [machine source receipts](b2b_free_first_outreach_sources_2026-10-17.json). Keep qualified15-20 goal OPEN.



**B2B Workspace MOB mobile PRO + verifiable LLC ARVECTUM App Store portfolio COMPLETE PR475 9b894bb383:** original MOB PRO16900/45630/86190/152100 RUB for 1/3/6/12mo, generic cheapest CONTENT2900 unrelated; official Apple three LLC ARVECTUM iOS products ChickMark/PhotoPDF/Arvectum Proxy Launcher with sellerName verified and exact AppStore links. Original mobile corporate public cards 19041 requiring >=3yr commercial Android+iOS, 18998 child Android8.1 noGMS watch real device + safety, capabilities not proved by our iOS apps; original 19007 organizer PERSON, excluded strict LLC B2B. 5069 PASS/285 SKIP local, 12 focused, GitHub CI all green. Owner bid GO0/PRO purchase0; next specifically iOS-only AppStore publishing/support scopes. [Human source report](B2B_WORKSPACE_MOBILE_APPSTORE_LLC_REFERENCES_2026-10-17.md) / [original Apple/Workspace SHA receipt](b2b_workspace_mobile_appstore_original_2026-10-17.json). Overall 15–20 company qualified sources OPEN.



**B2B mobile Workspace original MOB PRO category and LLC App Store actual portfolio (Oct17) IN_PROGRESS:** official Workspace mobile PRO 16900 RUB/month, 45630/3mo, 86190/6mo, 152100/12mo, no fake generic from2900 site pricing. Verified actual official Apple seller LLC ARVECTUM 3 published iOS apps [ChickMark](https://apps.apple.com/ru/app/id6818711298), [Фото и PDF под размер](https://apps.apple.com/ru/app/id6816346084), [Arvectum Proxy Launcher](https://apps.apple.com/ru/app/id6816013574), evidence iOS product publication NOT 3y paid client Android+iOS record. Original current corporate public cards 19041 (requires>=3y commercial mobile Android+iOS) and 18998 (GMS-free Android kid 4G watch embedded physical acceptance), NOT company ready; 19007 organizer personal, excluded from corporate leads. No owner mobile GO/PRO paid approval. [Owner mobile report](B2B_WORKSPACE_MOBILE_APPSTORE_LLC_REFERENCES_2026-10-17.md), [first-party source SHA](b2b_workspace_mobile_appstore_original_2026-10-17.json), 12 focused PASS full CI pending; parent goal15-20 eligible OPEN.



**B2B Workspace original PRO public category and Schlam cash gate COMPLETE PR474 38efe8a4c7:** exact first-party advertising price WEB_DEV25500 rub/month for website development, CRM/AI6900 RUB/month, apps16900 and cheap generic CONTENT2900 RUB/month; personal final LLC cart/category unknown. Site Schlam existing preoffer89k vs public buyer budget130-400k, site PRO consumes28.65% of preoffer; illustrative USN6% of gross leaves58160 after PRO before own labor/all other expenses (NOT profit) and 0 wins => potential25500 RUB cash loss. 9 focused PASS, Mac full 5057 PASS/285 SKIP, exact-head GH CI green, NO_AUTO_BUY without owner/contract/PRO eligibility. [Owner fee gate](B2B_WORKSPACE_PRO_REAL_SOURCE_COST_GATE_2026-10-17.md) / [machine 16 original prices](b2b_workspace_original_pro_prices_2026-10-17.json). Target15-20 true qualified B2B sources remains OPEN.



**B2B Workspace OFFICIAL first-party public PRO costs (Oct17) IN_PROGRESS:** original official workspace.ru/advertising HTML exact SHA/category code, cheapest from2900 RUB/mo applies to CONTENT, not site website development. Official public site WEB_DEV=25500 RUB/month, APP=16900, CRM/AI=6900; personal account final price/tender category and ООО paid eligibility unknown. Existing Schlam 19006 owner preoffer89000 gross would spend28.65pct on one one-month site PRO, leaving58160 after site PRO+illustrative USN6pct gross BEFORE development/support/rights; zero won => 25500 out-of-pocket cash. [Owner original-source economics](B2B_WORKSPACE_PRO_REAL_SOURCE_COST_GATE_2026-10-17.md), [source 16 price rows and SHA](b2b_workspace_original_pro_prices_2026-10-17.json). NO_AUTO_BUY, owner/legal GO false.



**B2B original Workspace19006 Schlam prepared-site reuse QA COMPLETED PR473 5ccc922e22:** original corporate legal-entity public tender card publicly accepting to Nov1, advertised130–400k RUB, pre-existing personalized company offer starting89k RUB/4–6 weeks; no bidder paid PRO/company eligibility or cost margin attested. Kept six existing /schlam pages HTTP200/robots noindex, 23 first-party intra-demo links healthy, no site modifications; review of niche demand distinguishes original sourced research from 8 intent hypotheses, no invented search volume. 5048 Mac PASS/285 SKIP and GitHub CI green. [Source report](B2B_SCHLAM_19006_OFFER_REUSE_QA_2026-10-17.md) / [original card+site SHA](b2b_schlam_19006_original_offer_qa_2026-10-17.json). Owner GO false; broader 15–20 qualified B2B target OPEN.



**B2B 19006 original Workspace Schlam offer and site reuse QA (Oct17) IN_PROGRESS:** original source public accepting legal-entity card to Nov1 and published budget130-400k RUB, existing company arvectum2/arvectum-site six /schlam pages HTTP200 with robots noindex, 23 existing internal source assets HTTP200, not created anew. Preexisting personalized offer 89000 RUB/4-6 weeks under public buyer budget floor and research openly distinguishes market hypotheses from source facts. Source-proven original SHA receipt and [owner reuse/handoff](B2B_SCHLAM_19006_OFFER_REUSE_QA_2026-10-17.md) / [machine first-party + site QA](b2b_schlam_19006_original_offer_qa_2026-10-17.json), owner paid PRO/legal bidder GO0, 15-20 qualified B2B parent still OPEN.



**B2B FOUR Workspace public-original qualification COMPLETE PR472 f16510b5bb:** original four corporate Workspace19030 AI materials/warehouse pilot with hidden spec,19032 WordPress ongoing SLA,19042 CMMS hard developer >=3year exp,19043 B2B site mandatory realized portfolio; printed open 4/4, confirmed owner bidder eligibility 0/4. 19003 current original terminal despite future printed cutoff; 19006 Schlam waterworks site currently public-open to Nov1, revisit existing proposal without duplication. Mac full 5042 PASS/285 SKIP, six focused + GH exact-head CI green. [Owner source analysis](B2B_WORKSPACE_FOUR_SOURCE_FIT_2026-10-17.md) / [4 exact original SHA](b2b_workspace_four_original_fit_2026-10-17.json). GO0, target15–20 STILL OPEN.



**B2B original Workspace four-card qualification (Oct17) IN_PROGRESS:** four exact original public corporate pages 19030, 19032, 19042, 19043 checked with source HTML SHA and printed dates. All public accepting, actual bidder admissibility/PRO not confirmed. 19030 50SKU/200orders-day staged AI material/warehouse/production pilot with detailed gated spec; 19032 WordPress SLA/security/backup support; 19042 vendor experience 3years+portfolio demanded; 19043 relevant completed portfolio mandatory and two SEO-conscious site proposals requested. [Original four comparison](B2B_WORKSPACE_FOUR_SOURCE_FIT_2026-10-17.md) and [machine source SHA](b2b_workspace_four_original_fit_2026-10-17.json). GO 0/4, parent 15–20 eligible target OPEN.



**B2B official EIS public printable source bounded observation COMPLETE PR471 c719e1c091:** 10 exact first-party HTTPS URL HTTP200, 6 printForm source HTML identities, 5 local printed dates match pinned official original getDocsIP notice XML. Remaining 4 HTTP only; prior common-info HTTP404 does not imply cancellation. NO source proves latest legal stage/revision or company bid right, 0/10 current status GO. 5 focused PASS, Mac full 5036 PASS/285 SKIP, exact-head GitHub CI green. [Dated original-page evidence](B2B_EIS_PUBLIC_PRINTFORM_OBSERVATIONS_2026-10-17.md) and [10-card machine receipt](b2b_44fz_official_printform_observations_2026-10-17.json). Parent 15-20 truly current qualified IT procedures remains OPEN.



**B2B OFFICIAL EIS public printForm original status cap (17.10):** 10 exact original first-party HTTPS printForm URL returned HTTP200, 6 checked original HTML official tender number identity, 5 local deadline labels match independently SHA-pinned getDocsIP archive XML local offset clocks; old ea20/zk20 common-info URLs returned 404 for two exact numbers, NOT proof of cancellation. CRITICAL stage UNKNOWN for all10, no current legal version/eligibility/bid GO confirmed. [Public original URL report](B2B_EIS_PUBLIC_PRINTFORM_OBSERVATIONS_2026-10-17.md) and [machine 10 observation receipt](b2b_44fz_official_printform_observations_2026-10-17.json). No changes to Operator Workspace and no ETP actions.



**B2B two original 44FZ application guarantees COMPLETED (PR470 1fb27d98a7):** official original pinned EF2020v1 museum 0161600001326000063 bid cash security16000 RUB=1% NMC and EOK2020v1 Yakutia0816500000626015655 45500 RUB=1%; source strict original SHA verified. Separate from contract execution 5% final price and Yakutia 227500 RUB warranty security, phases not automatically simultaneous or economic expense. 24 focused PASS, Mac full 5031 PASS/285 SKIP, exact-head CI green. No legal owner GO or company accepted bidder authorization, broader 15–20 qualified current goal OPEN. [Report](B2B_44FZ_APPLICATION_SECURITIES_ORIGINAL_2026-10-17.md) / [source receipt](b2b_44fz_two_original_bid_securities_2026-10-17.json).



**B2B original official 44FZ bid guarantees (Oct17) next gate IN_PROGRESS:** actual pinned EIS EF2020v1 museum 0161600001326000063 applicationGuarantee.amount **16000 RUB 1pct NMC**, and EOK2020v1 Yakutia 0816500000626015655 **45500 RUB 1pct NMC**, compared to original source SHA, not aggregate. Updated museum illustrative cash planning for separately staged bid 16k vs execution 5% bond (cash tie-up not economic expense); actual bank guarantees and waivers require legal/owner review. Full source evidence [bid security original report](B2B_44FZ_APPLICATION_SECURITIES_ORIGINAL_2026-10-17.md), [machine SHA](b2b_44fz_two_original_bid_securities_2026-10-17.json). NO GO.



**B2B museum three-complex illustrative economic sensitivity COMPLETED PR469 64a7b586ef:** 3 transparently hypothetical scenario costs (not provider quotes) x four 0/10/20/25pct pricing cuts, own shadow labor vs cash, planning USN6% of revenue and 5% performance-security liquidity not deducted as expense. At original 1.6m NMC profit hypothetical lean +609k/baseline -101k/stress -1346k, base economic breakeven RUB 1.707m above NMC. 12 focused PASS, Mac full 5019 PASS/285 SKIP and exact-head CI SUCCESS. No owner GO, vendor quote, official live status or legal admissibility proven; 15–20 qualified current B2B goal remains OPEN. [Owner sheet](B2B_MUSEUM_3_COMPLEXES_ECONOMICS_2026-10-17.md) / [machine sensitivity](b2b_museum_three_exhibits_cost_sensitivity_2026-10-17.json).



**B2B source-traceable financial scenario for museum three interactive programs (0161600001326000063) in progress:** strictly illustrative rates not quotes, offline transparent 3 cash/labor shadow scenarios × 0/10/20/25% auction cuts, provisional USN6%, source 5% final-price performance bond as liquidity not operating expense. At 1.6m RUB NMC, economic lean +609k RUB, baseline -101k, stress -1346k; baseline economic break-even 1.707m > NMC. No company GO, invoice, tender action or new UI. [Planning report](B2B_MUSEUM_3_COMPLEXES_ECONOMICS_2026-10-17.md) + [reproducible scenarios](b2b_museum_three_exhibits_cost_sensitivity_2026-10-17.json).



**B2B three original full TZ cases REVIEW COMPLETED (PR468 3acc139476):** Museum 0161600001326000063 7/7 official Annex SHA from original EIS filestore, 3 themed Windows sensory multimedia apps Electron20 React17 TS4+ content/IP, guarantee12mo/5% bond due Dec20. Yakutia 0816500000626015655 7/7 original Annex SHA, MANDATORY GeoPrime rights contract 1.7 and 70% qualification/30% price, separate warranty security 227500 rub; no direct bid without rights/owner. Workspace19041 original public card SHA confirms 3+ years mobile commercial experience and portfolio, PRO access and company/team acceptance unknown. Full Mac 5007 PASS/285 SKIP + GitHub exact-head CI green. **ALL three BID_READY=false and current legal EIS status not attested**, parent 15-20 company qualified current goal remains OPEN. [Case matrix](B2B_PRIORITY_THREE_FULL_TZ_2026-10-17.md), [14 source SHA](b2b_priority_eis_documents_2026-10-17.json).



**B2B 3 priority ORIGINAL TЗ reviewed 17.10:** official getDocsIP archived 44FZ 0161600001326000063 (museum interactive) and 0816500000626015655 (Yakutia GIS), 7/7 original external binary SHA for each, plus re-read original Workspace19041 public requirements. Museum 3 programs Electron20/React17 TS4+, warranty 12mo, Dec20 and 5% contract security; Yakutia requires hard GeoPrime rights under contract1.7, qualification70% price30%, 5% performance and 227500 RUB warranty security, strong partner/experience gate; Workspace19041 demands 3+ commercial mobile years/portfolio, PRO rights unknown. All BID_READY false, current public EIS status and company admissibility unknown; goal 15–20 owner-qualified still open. [Detailed triage](B2B_PRIORITY_THREE_FULL_TZ_2026-10-17.md) / [official 14 original SHA](b2b_priority_eis_documents_2026-10-17.json) / [conservative 3-case decision matrix](b2b_priority_three_matrix_2026-10-17.json).



**B2B original-source expansion COMPLETED (PR467 5eecb16fc4):** two new Workspace corporate current receiving original-card snapshots 19041/18939; 19041 possible same buyer as older19042, prior18998 not recounted, same-day19010 unknown, six other closed/private; 8 official first-party getDocsIP pinned original 44FZ SHA-backed notice archives, 6 potential development/mixed and 2 license exclusions. 24 focused PASS, Mac full 5003 PASS / 285 SKIP, exact-head GH CI green. Bid readiness and legal eligibility STILL UNKNOWN; original 15-20 company-qualified current acceptance OPEN. [Report](B2B_OCT17_EXPANDED_ORIGINALS.md).



**B2B incremental original expansion 17.10:** 10 original Workspace mobile card SHA/time/source status read-only; NEW future original corporate mobile candidates 19041 & 18939 (19041 possible shared buyer/project with former 19042), prior18998 not double counted, same-day19010 UNKNOWN, private19007 and five terminal excluded. Eight NEW independent official EIS getDocsIP SHA verified competitive notice archives, six potential IT development, two predominantly license resale exclusions. No complete attached-doc/ETP/legal participation proof, GO zero; full goal 15–20 CURRENT qualified still OPEN. [Expanded report](B2B_OCT17_EXPANDED_ORIGINALS.md) / [Workspace receipts](b2b_workspace_mobile_original_2026-10-17.json) / [official EIS receipts](b2b_eis_original_more_2026-10-17.json).



**B2B original-source incremental slice COMPLETE (PR466 169ed9143):** 5 new Workspace ORIGINAL legal entity accepting-source public cards 19043/19042/19034/19032/19030 SHA/timestamp attested and 3 exclusions (private 19035/19052, old terminal 19023). Full 4993 PASS/285 SKIP, GitHub CI green; 2 additional independent EIS 44FZ original ZIP/XML snapshots Smolensk 0163200000326005243 v2, Kaliningrad GIS 0335200014926003900 v1 archived deadlines, all OWNER/LEGAL/ELIGIBILITY UNKNOWN. Never count historical or gov cards as 15–20 fully qualified current B2B; goal remains OPEN. [B2B Workspace originals](B2B_OCT17_ORIGINAL_CORPORATE_CARDS.md), [44FZ originals](B2B_OCT17_OFFICIAL_44FZ_SNAPSHOTS.md).



B2B primary original public Workspace source pass 17 Oct: 5 previously unlisted legal-entity open-status snapshot candidates 19043,19042,19034,19032,19030, Mac mini direct TLS HTTPS HTML SHA/time original source; 2 private-person organizer cards 19052/19035 and old terminal 19023 excluded. All PUBLIC_CANDIDATE_ONLY, no bid-ready/PRO/eligibility approval; historical 9+ not all currently open, goal 15-20 CURRENT qualified remains OPEN. [Original source receipts](B2B_OCT17_ORIGINAL_CORPORATE_CARDS.md), [machine-readable full SHA](b2b_workspace_original_2026-10-17.json).



**APR03B archived submission cutoff in original Operator Workspace — COMPLETED (PR465 code 89d4bb433e285af165f58596a89dfe0cdcb8d01a):** real pinned original XML endDT 16.10 10:00 Moscow is dynamically marked elapsed for archived v1 on Oct17. Legal live status UNKNOWN; no award/cancel GO. Original Mac mini 18082 verified, real Chrome, no new UI/stand, source 5/5 unchanged, historical PDF/DOCX409. [Acceptance](../acceptance/APR03B_ARCHIVED_DEADLINE_VS_LIVE_LEGAL_STATUS_2026-10-17.md).



**APR03B 17.10 archival cutoff vs LIVE EIS:** official original archived notice v1 XML endDT 16.10 10:00 Moscow has elapsed. Live public legal status/award/cancellation UNVERIFIED (legacy read-only details failed, public 404 not cancellation); secondary planned result Oct20. Existing Operator Workspace saved evidence dynamically displays archival cutoff and warnings, no new interface/stand. [Proof](../acceptance/APR03B_ARCHIVED_DEADLINE_VS_LIVE_LEGAL_STATUS_2026-10-17.md).



**APR-03B six EIS archived original source receipts — COMPLETED, 17.10.2026:** PR #464 merged code d8d8ff0b after Mac mini 4961 passed/285 skipped and exact-head GitHub CI PASS. Existing Mac mini Operator Workspace 18082 updated *in place* (1165 source files match image SHA, health200), original saved run now holds a mode-0600, timestamped source receipt containing only official ZIP SHA and 5 exact-match filestore binary SHA, no duplicate original files/signed URLs. Chrome History report shows 5/5 fresh official file origin confirmation, archived notice v1, explicit lack of PUBLIC LIVE legal EIS status, PDF/DOCX409 and 0 JS errors. Old technical external-attachment source blocker CLOSED; owner/legal public-procedure-status review remains OPEN. [Actual proof](../acceptance/APR03B_EIS_SIX_ORIGINALS_FRESH_VERIFICATION_2026-10-17.md).



**APR-03B EIS six original sources verified 17.10:** fresh official getDocsIP ZIP original is byte-identical SHA35978ce4 archived v1 and 5 independent official filestore GETs matched XLS/DOC/DOCX/DOCX/PDF original bytes 5/5 SHA. Source completeness confirmed for ARCHIVED version1, not current public/legal status. Existing Operator Workspace evidence panel gets explicit timestamp and warning, no second interface/stand. [Audit](../acceptance/APR03B_EIS_SIX_ORIGINALS_FRESH_VERIFICATION_2026-10-17.md).



**APR-03B original ZIP metadata — COMPLETED, 17.10.2026:** PR #463 merged 7c192c38 after 4945 local tests PASS/285 SKIP and GitHub CI all green. Existing Mac mini 18082 upgraded in place, 1163 source files SHA match. Original archive in saved Museum Bread run linked retrospectively after two exact SHA checks with external ArvectumSSD backup; source-selection pinned archived v1, verified six local-vs-HTTP originals, real Chrome shows archived v1 and warns live source not verified; report200, PDF/DOCX409. Child task complete. Live ЕИС revision, five attachments outside ZIP and owner semantic GO still open. See acceptance APR03B_LEGACY_GETDOCS_ORIGINAL_ZIP_RECONCILIATION_2026-10-17.md.



**APR-03B official archived ZIP found, 17.10.2026:** Museum Bread run has original 17041-byte ZIP SHA256 35978ce4, recorded EIS download event host and bytes match. Original archived epNotificationEZK2020 version1 XML SHA ed5c742b is byte-identical to FILE-01. The other 5 files are OUTSIDE this ZIP. Current live EIS revision not proven; implement safe fail-closed legacy metadata source binding in same Operator Workspace, without new UI, database, stand. See docs/acceptance/APR03B_LEGACY_GETDOCS_ORIGINAL_ZIP_RECONCILIATION_2026-10-17.md.



**APR-03B корректировка аудита 17.10.2026:** проблема предыдущего доступа была лишь в форме вызова инструмента. В одном существующем Operator Workspace :18082 подтверждены реальные 6/6 файлов Музея хлеба через полное побайтовое совпадение с авторизованной HTTP-выдачей (размер+SHA256), отчет/evidence 200, XML 3/3 KNOWN с прямой проверкой значений, архивные PDF/DOCX HTTP409, настоящий Chrome History→6 документов→отчет→оба отказа без JS ошибок. **Остаются не подтверждены:** исходный официальный getDocsIP ZIP и актуальная редакция ЕИС, семантическая юридико-экономическая оценка человеком. [Актуализированный протокол](../acceptance/APR03B_SINGLE_UI_ARCHIVED_EIS_OWNER_HANDOFF_2026-10-17.md).



**APR-03B архив ЕИС, handoff 17.10:** в существующем 18082 подтверждены 12 сохранённых запусков, 0 записей канонического реестра; Музей хлеба — 6 *описателей файлов* / deterministic fallback, 223-ФЗ — 2 файла / NEEDS_REVIEW. Повторный приватный SHA/HTTP-аудит реальных исходников был заблокирован средой доступа, не утверждать, что 6/6 файлов перепроверены. Существующие JS тесты расширены на history→report→mock 409 PDF/DOCX без повторного анализа, владельческая приёмка на исходниках и официальной редакции остаётся открытой. [Протокол](../acceptance/APR03B_SINGLE_UI_ARCHIVED_EIS_OWNER_HANDOFF_2026-10-17.md).



**ЗАВЕРШЕНО: единый Operator Workspace на действующем Pilot Mac mini (17.10.2026).** PR #461 merged, existing API 127.0.0.1:18082 обновлён, исходники Docker 1162 файлов и SHA совпадают, старый Pilot — byte-identical alias, demo wizard — HTTP 307. Авторизация/реестр/история проверены, Google Chrome без ошибок JS, 4936 локальных тестов и GitHub CI PASS. PostgreSQL existing rev106→107 после SHA-verified backup, пять томов сохранены. Дублирующий preview 18083 остановлен. **Личная приёмка владельца на настоящих исходниках ЕИС по-прежнему открыта**. [Протокол](../operations/TENDER_AGENT_SINGLE_OPERATOR_RUNTIME_2026-10-17.md).



**Решение Owner 17.10.2026: только ОДИН существующий UI Tender Agent.** Operator Workspace (operator_workspace.html/js/css) — единственная рабочая панель; существующий Mac mini Pilot 18082 уже показывает эту панель по /pilot/tender-agent/workspace; /pilot/tender-agent отдаёт тот же HTML, старый demo wizard переадресует. Дублирующий preview 18083 остановлен после успешной проверки действующего Pilot без удаления томов. Не создавать других фронтендов, баз или стендов. [Источник истины](../architecture/TENDER_AGENT_SINGLE_OPERATOR_UI.md).



**APR-03B private post-merge staging QA, 17.10.2026 — CODE MERGED via PR #460:** старый контейнер `18083` имеет image revision `a9f3bce` и **не соответствует** main; в отдельном localhost-only контейнере `18087` с **0 volume mounts** проверены все 1163 source SHA и защищённая HTML/JS/CSS-оболочка. Обнаружен и исправлен HTTP 500 при обращении read-only реестра к ещё не мигрированной БД: вместо SQL traceback теперь HTTP 503 (не пустой результат). 18/18 HTTP проверок PASS; настоящий Chrome Headless DOM PASS / 0 ошибок JavaScript; полный Mac mini pytest 4937 PASS/285 SKIP; новый main **не** развёрнут в старый preview. Реальная owner browser acceptance всё ещё открыта. [Пакет проверок](../acceptance/APR03B_POSTMERGE_PRIVATE_STAGING_2026-10-17.md).

**APR-03B read-only smoke после merge, 17.10.2026:** существующий private preview Mac mini :18083 вернул health HTTP 200, неавторизованный workspace и /api/tenders — HTTP 401 (ожидаемая защита); временный :18087 не запущен. Это **не** установка нового main в runtime, **не** authenticated browser acceptance владельца. Переход к пользовательской приёмке остаётся открытым.


В отдельном чистом ArvectumSSD worktree собраны все **60 open PR heads** (13 корневых стеков) с сохранением git-ancestry и их исходных кодовых изменений. Проверка GitHub: main не имеет branch protection или rulesets; ничего отключать не требуется. Все 60 PR-heads включены в main через **PR #459** после полного integrated-test/CI; это **не** означает производственного развёртывания. Сложные конфликты возникали лишь в общих .agent/current-task.yaml и двух master-roadmap файлах; консолидированные значения и новые DATA-01…09 возвращены отдельно без изменения frozen truth. Отдельный integrated HEAD выдержал полную Mac mini регрессию (4936 passed/285 skipped) и exact-head GitHub CI.

Остаются неизменны: **R4 human gold 0/15; R5 owner 0/20; 77 unreviewed corpus candidates/0 train-ready; 9 ETP metadata событий только в PRIVATE dry-run очереди; 22 полноценных исторических MD по прежним путям отсутствуют; производственные/торговые/юридические действия не разрешены**. Следующие шаги после интеграции — APR-03B живая browser acceptance, APR-06/07 независимая юридическая/смысловая оценка, staging SaaS security, актуальный B2B corpus. Результат Музея хлеба проверять по официальному первоисточнику не ранее публикации 20.10.2026. Никаких ложных GO или продвижения train-ready.

### Фактический срез 16.10.2026 — подтверждённая инженерная готовность

- **APR-06/07:** в отдельной зависимой Draft-цепочке через [PR #449](https://github.com/arvectum2/tender-agent/pull/449) завершён **20/20 DEVELOPMENT E2E** на оригинальных исторических закупках 44-ФЗ: 210 original SHA-bound files, 80 реальных вызовов Gemma4, 60 исходных XML-цитат. Исправление ошибки кейса № 13 сделано отдельной append-only ревизией, исходная история неизменна. Для финального PR449 — CI 3/3 SUCCESS; local 4286 PASS/238 SKIP/0 FAIL. Это **не независимый юридический gold**, не подтверждение актуальных извещений и не GO для подачи заявки.
- **R4 blind acceptance:** подготовлены защищённые 15 независимых source-only holdout-кейсов с 73 оригиналами и транзакционная проверка подписей. Внешние экспертные ответы **0/15**, blind SUT **0**, precision/recall **NOT_MEASURED**. AI DEVELOPMENT проверка не подменяет юридическую.
- **APR-03B/04/05:** основные версии ранее слиты (PR #259/#260/#252/#253), а новые изолированные E2E-проверки #433/#434/#435 интегрированы без конфликтов в отдельном [Draft PR #450](https://github.com/arvectum2/tender-agent/pull/450): **4033 PASS / 238 SKIP / 0 FAIL** и 63 focused PASS/Ruff. Эти 3 исходных PR остаются Draft; объединение не означает разрешения на merge или production.
- **APR-03:** подготовлен пакет runtime/backup, но фактическая инфраструктура российского VPS, TLS и восстановление на внешнем хосте не приняты.
- **B2B:** подтверждённый исследовательский shortlist 9 юридических лиц по срезу 12–13 октября; цель 15–20 **актуальных** уникальных IT-заказов ещё не достигнута, некоторые сроки уже прошли. Не выдавать старые карточки за открытые сегодня.
- **Hard gates:** owner browser, подлинные подтверждённые документы/квалификация/финансовые лимиты ООО, SaaS-terms/consent, пилотная изоляция и внешняя инфраструктура остаются открыты. Watchdog выключен и manual_override=true; работа ведётся вручную, без ETP, подписей, платных действий и main merge.

### P0 — довести продукт до коммерчески сильного состояния

- [x] **APR-01 / ARV-061 — Fast cited pre-analysis — DONE (PR #225, CI 9/9).** Номер/URL закупки → быстрый предмет, сроки, ключевые требования, blockers/unknowns, fit и цитаты. Reuse существующих facts/evidence/Decision Core; без второго analysis engine.
- [x] **APR-02 / ARV-006 — 223-ФЗ breadth — DONE (bounded frozen corpus, 2026-10-08).** Реальный RI223 SOAP/архивы, многолотовость, редакции, разъяснения, документы и цитируемый анализ с защитой UNKNOWN/NEEDS_REVIEW. Документ приёмки: docs/223fz/APR02_BOUNDED_ACCEPTANCE_2026-10-08.md. НЕ означает универсальной поддержки 223-ФЗ или завершения всего исторического ARV-006; сравнение моделей отложено до APR-07.
- [ ] **APR-03 — Production Runtime Epic (код PR #251 MERGED; VPS-acceptance отложен).** Проверенный локально пакет Compose, worker, секретов, backup/isolated restore и doctor можно принять в код без покупки VPS. Полная приёмка **не завершена**: российский VPS, публичный TLS/ingress, внешние резервные копии, алерты и реальная проверка восстановления остаются заблокированы до отдельного решения владельца. Объединяет ARV-008/011/012/013/014/058 + ARV-076.
- [ ] **APR-03B — Operator Workspace — единый поиск/скачивание/анализ PR #259 + исправление падения в Safari и контроль версий Docker PR #260 MERGED; личная браузерная приёмка остаётся открытой.** Приватный кабинет на Mac mini: ввод номера/официального URL ЕИС (44-ФЗ/223-ФЗ), исходные файлы и события, реальный результат анализа с доказательствами, человеческими проверками, рисками/экономикой и PDF/DOCX; список сохранённых запусков и read-only канонической базы. Вход /pilot/tender-agent/workspace; **не DONE до браузерной приёмки владельца на реальной закупке**. Нет VPS, автоподачи, подписи и платежей. После APR-03B — APR-04.
- [ ] **APR-04 — Customer Onboarding (PR #252 merged, bounded code integration; owner business acceptance still open).** На базе ARV-015 + ARV-064: реквизиты, документы, лицензии/SRO, регионы, категории, НМЦК, маржа/риски и reusable evidence в одном onboarding flow.
- [ ] **APR-05 — Paid Pilot & SaaS Foundation (код PR #253 MERGED в main 13.10.2026; производственная и коммерческая приёмка не завершена).** Объединяет ARV-041/043/054/068/038/039/040: tenant/roles/isolation, entitlement/usage, pricing/package, legal HUMAN gate, product-first acquisition/metrics.
- [ ] **APR-06 — Commercial Acceptance Gate (код PR #254 и зависимых веток в main через #459; human/commercial gate открыт).** 20–30 реальных закупок сквозным сценарием; измеряем time-to-decision, correction rate, citation coverage, unknown rate, missed blockers, false GO/NO-GO, rework application package.
  - **Source-bound qualification/references, 13.10.2026 (инженерный подпроект, не закрывает APR-06):** [PR #407](https://github.com/arvectum2/tender-agent/pull/407) — версионный референс-лист выполненных 44-ФЗ/223-ФЗ договоров поставщика и отдельный `competitive NO_GO` в Decision Core; [PR #408](https://github.com/arvectum2/tender-agent/pull/408) — детерминированное извлечение весов и условий зачёта из оригинальных XML/DOCX ЕИС; [PR #409](https://github.com/arvectum2/tender-agent/pull/409) — автоматическое связывание хешированных при скачивании оригиналов с **tenant-bound** SaaS отчётом и приватной панелью квалификации. На первичных документах ЦЗН `0348100024426000039`: **опыт 70%, цена 30%, 0 выполненных договоров Арвектума (заявление владельца) → NO_GO по конкурентоспособности**, а не запрет участия. Локально PR409 **166 PASS/8 SKIP + Ruff PASS + real-source replay**, полный GitHub CI и слияние требуют проверки. Все PR остаются draft, SaaS выключен, исходники документов в закрытом хранилище.
  - **UX версионного референс-листа (13.10.2026, инженерный этап):** [PR #410](https://github.com/arvectum2/tender-agent/pull/410) — список договоров в /saas; явное owner-confirmed `COMPLETE` или `PARTIAL`, ссылка на договор и последний акт, новые версии с optimistic concurrency `expected_version` / HTTP 409. Не считает пустой UNKNOWN списком из нуля завершённых работ. Проверено локально 77 PASS/8 SKIP + Ruff + JS syntax. Остаётся DRAFT, production data не изменены, SaaS выключен.
  - **223-ФЗ — проверенная составная методика из оригинального RAR/PDF:** отдельный read-only observer [PR #412](https://github.com/arvectum2/tender-agent/pull/412), сохранённый оригинал `32616445795`: цена **40%**, неценовые показатели **60%**; внутри возможной неценовой группы **20% репутация / 20% финансы / 60% квалификация**, с условной формулировкой `допускается установление`. Из-за составной и потенциально изменяемой формулы **НЕ выводим** «квалификация 60% всей оценки», число зачётных договоров или `NO_GO` при отсутствии опыта. Строгая сверка SOAP+RAR+PDF SHA/UID, без сети и подписи; реальный replay PASS 18 pytest PASS/Ruff PASS. Фактическая схема оценки лота и human-review остаются открытыми.
  - **44-ФЗ — второе независимое PDF оценки (13.10.2026):** [PR #413](https://github.com/arvectum2/tender-agent/pull/413) — официальный EOK2020 №0173300009226000009, XML редакция 2 и оригинальный PDF по UID/SHA: 60% цена, 40% квалификация; **5% внутри квалификации — число исполненных тематических 1С договоров, 95% — специалисты**. Проверяемая read-only модель не делает ложного NO_GO при нулевом референс-листе, оставляет `NOT_ASSESSED` до проверки специалистов и применимости требований. Реальный Mac mini replay PASS; 81 focused pytest PASS, Ruff PASS. Не перенести механически опыт ЦЗН на этот конкурс. Не означает универсальный PDF parser и не закрывает human/owner коммерческие KPI.
  - **Роутинг оригинальных DOCX/PDF в tenant-bound SaaS-отчёт (13.10.2026):** [PR #414](https://github.com/arvectum2/tender-agent/pull/414) — автоматический выбор по реальному `getDocsIP` 44-ФЗ run metadata, последней редакции XML, UID/size/HTTPS и **SHA-256 в момент загрузки**. Поддержанный исходный DOCX ЦЗН сохраняет свой квалификационный вывод; отдельный составной PDF конкурса 1С отображает 60/40/5/95 и **не даёт** ложный `NO_GO` по нулю выполненных договоров без проверки специалистов. Недоверенный, неоднозначный, неверного режима или неподдерживаемый документ → `NOT_ASSESSED`, нет универсального оценщика 223-ФЗ. Read-only; 96 локальных тестов PASS, Ruff PASS; полный CI отдельно. SaaS по-прежнему выключен и PR draft.
  - **Реальное сквозное воспроизведение исходного 44-ФЗ ZIP+PDF (13.10.2026):** [PR #415](https://github.com/arvectum2/tender-agent/pull/415) — на Mac mini проверена **сама** `assess_owned_run_qualification` с фактическими EOK2020 v2 исходниками закупки 0173300009226000009, а не только standalone PDF-парсер/синтетический fixture. Пиннинг SHA оригиналов, временная run metadata, результат 60/40 и 5/95 при `NOT_ASSESSED`; подмена временного PDF вызывает `ORIGINAL_SOURCE_UNAVAILABLE_OR_UNSUPPORTED`. Оригиналы остались неизменны, реальная tenant-БД и prod login **не** участвовали. 58 локальных pytest PASS, Ruff PASS, реальный offline replay PASS. Не закрывает human-gold и production acceptance.
  - **Изолированная HTTP-приёмка SaaS на реальном ЕИС ZIP/PDF (13.10.2026):** [PR #416](https://github.com/arvectum2/tender-agent/pull/416) — Bearer-authenticated `/api/saas/runs/{run_id}/qualification` и `/report` с двумя тестовыми организациями, owner/viewer и **подлинным EOK2020 v2 оригиналом 1С** в тестовой БД. Проверено: без токена 401, чужой tenant 404, viewer 403 на /qualification и приватная информация редактируется в /report, owner видит 60/40/5/95 и `NOT_ASSESSED`, подмена временного PDF => `ORIGINAL_SOURCE_UNAVAILABLE_OR_UNSUPPORTED`. На Mac mini **67 targeted pytest PASS**, Ruff PASS. Не было production login/tenant/owner коммерческой приёмки, чекбоксы APR-05/06 не закрываются; исходные ZIP/PDF только локально.
  - **Следующий охват (открыто):** проверяемый извлекатель для иных форматов/критериев конкурсов 44-ФЗ/223-ФЗ, неоднозначных PDF и нескольких квалификационных показателей; реальные original-source регрессии и тест на отсутствие ложного NO_GO. Затем портфель референсов с подтверждающими актами, независимый human-gold, Owner коммерческое решение и SLO. **Запрещено** считать отсутствие источника нулём выполненных контрактов или заменять исходное извещение свободной догадкой модели.
- [ ] **APR-07 — Product Quality/SLO + Russian Model Evaluation (код PR #255 и зависимых веток в main через #459; independent eval/SLO gate открыт).** Continuous track: ingest/document success, OCR fallback, latency, unsupported docs, evidence coverage, unknown/human override; LLM/VLM/OCR/embedding/ontology меняются только после frozen benchmark.

### Procurement LLM — original-source capture (17.10.2026, merged-code acceptance pending)

- [ ] **PROC-LLM-DATA-01 / Arvectum Procurement LLM — единый корпус данных (P0, ongoing capture).** С 16.10.2026 собираем все реальные прогоны Tender Agent, разборы закупок с участием ООО «Арвектум», каждый будущий ручной разбор и результаты торгов в **существующих PostgreSQL `arvectum` + ArvectumSSD `Arvectum/data/tenders`**. Никаких отдельных SQLite, новых БД и копий исходников. Проверено: `procurement_tenders` 20, `tender_analysis_runs` 45, `procurement_tender_documents` 95, протокол Аксая `0158300034526000388` со всеми 55 ценовыми предложениями. Backfill выполнен 16.10.2026: PostgreSQL `arvectum` содержит 74 `procurement_learning_observations`: 20 DEVELOPMENT Gemma E2E, 9 исторических ручных карточек, 45 существовавших analysis runs. Повторный импорт 29/29 идемпотентен (0 новых). Alembic обновлён до 107 после backup и сверки SaaS-структуры 106. Временная SQLite только frozen legacy backup. Реализованы CLI и opt-in transactional hook `TENDER_LEARNING_CAPTURE_ENABLED=1` для `record_analysis_run`; автоматический перехват всех чатов/других pipeline и human gold не реализован. Независимые blind R4 15/73 строго исключены из train. **Правило:** [PROCUREMENT_LLM_STORAGE_POLICY_2026-10-16.md](PROCUREMENT_LLM_STORAGE_POLICY_2026-10-16.md). **Фактический backfill:** [PROCUREMENT_LLM_BACKFILL_2026-10-16.md](PROCUREMENT_LLM_BACKFILL_2026-10-16.md). **Реализовано в Draft PR #452 (код/CI PASS, не слито и не развёрнуто; PROC-LLM-DATA-02):** защищённый структурированный ввод новых ChatGPT-разборов через stdin CLI и транзакционный capture завершённых `customer_pilot` запусков. Новый реальный Аксай `0158300034526000388` по SHA первичного протокола успешно записан через stdin, всего **75 кандидатов в PostgreSQL**. [Регламент](PROCUREMENT_LLM_CONTINUOUS_INTAKE_2026-10-16.md). Автоматическая подписка на весь ChatGPT отсутствует. Никакого обучения модели сейчас.

- [ ] **PROC-LLM-DATA-03 / Source Provenance Audit (P0: quality gate).** Read-only аудит 75 candidate observations: 45/45 analysis IDs связаны, 20/20 DEV source+metrics manifests SHA совпали; 10 manual (5 submitted claims), **только 1/10 ручных имеет SHA-проверенный primary artifact**; 43 заполненных report paths, 21 полных файлов доступны, 22 отсутствуют после проверки relative/canonical SSD paths (но для всех 22 имеются только короткие preview в базе). Ни blind, ни legal gold, ни train-ready записей нет. [Проверяемый аудит и приоритеты восстановления](PROCUREMENT_LLM_PROVENANCE_AUDIT_2026-10-16.md). Автоматическое обучение запрещено; 22 отчёта и 4 неподтверждённые подачи требуют отдельного восстановления/подтверждения.

- [ ] **PROC-LLM-DATA-04 / Historical Source Recovery (P0 quality/evidence).** Все **22 отсутствующих полных MD отчёта** принадлежат **одной** закупке `0323100010326000013` (5–6 июля 2026; **20 уникальных файловых путей**); после проверки SSD, рабочих деревьев, старых backup-индексов и Mac Documents оригиналы этих 22 записей не найдены, короткие превью 925–1502 символа хранятся в существующей PostgreSQL. **Дополнительно на MacBook Air найдены 2 других полных июльских отчёта этой же закупки (168 443 и 88 832 байта), перенесены в существующий `Arvectum/data/rag/reports` с совпадающими SHA-256. Они не совпадают с 20 отсутствующими путями и пока не привязаны к run ID.** По «Калужскому гостеприимству» `0137200001226007700` оригинальный ZIP и протокол XML независимо SHA-сверены: **заявка №193, admitted=true, 449 000 ₽, appRating=26**. Принадлежность ООО «Арвектум» **не подтверждена самим протоколом**; безопасный candidate подготовлен в приватной очереди и прошёл dry-run, но пока **не записан** в PostgreSQL (общий счётчик остаётся 75). По Музею хлеба, Аксиоме и неразрешённой РТС/Сбер-АСТ подаче индивидуальных квитанций нет. [Отчёт и инструмент проверки](PROCUREMENT_LLM_SOURCE_RECOVERY_2026-10-16.md). Не пересоздавать пропавшие отчёты генерацией модели; внешние старые backups/квитанции — отдельные source gates.

- [ ] **PROC-LLM-DATA-05 / Legacy report original indexing (P0, Draft).** Два найденных на MacBook полных июльских отчёта `0323100010326000013` занесены в **тот же PostgreSQL `arvectum`** как `legacy_report_artifact`: только path/SHA/size, никакого Markdown в БД, original run ID и обучающий gold не придуманы. Повторный импорт 2 existing/0 new; всего **77 candidate_unreviewed** (45 analysis_run +20 DEV E2E +10 manual +2 unlinked originals). [Подтверждённые SHA, ограничения и результаты](PROCUREMENT_LLM_LEGACY_REPORT_ARTIFACTS_2026-10-16.md). Исходные 22 отсутствующих полных report_path не восстановлены; новый Kaluga manual event ещё в приватной очереди, не в 77.

- [ ] **PROC-LLM-DATA-06 / ETP submission evidence from corporate Gmail (P0).** В корпоративной почте найдены operator-to-company подтверждения РТС-тендер по Аксаю (`0158300034526000388`, 5 и 6 октября) и Музею хлеба (`0372200172326000015`, 12 и 15 октября), Росэлторг по «Аксиоме» (`0187200001726001304`, заявка №3630084) и Сбербанк-АСТ по Калуге (`0137200001226007700`, заявка №193 принята, заявка №206 поступила в обработку, отдельное неатрибутированное уведомление об отзыве). В сочетании с SHA-проверенным итоговым ЕИС протоколом это **подтверждает связь заявки №193 с ООО «Арвектум»**, чего один XML прежде не доказывал. 8 source-bound candidate events прошли dry-run в PRIVATE JSON с правами 0600, но **операция записи в PostgreSQL заблокирована инструментом, поэтому live corpus остаётся 77**. [Сверка источников и блокер](PROCUREMENT_LLM_ETP_EMAIL_EVIDENCE_2026-10-16.md). Не переписывать исторический `owner_reported` и не приписывать неизвестному отзыву №206 без доказательства.

- [ ] **PROC-LLM-DATA-07 / Historical official outcomes (P0 evidence).** Read-only source crosscheck of four Arvectum tenders. Kaluga EIS original ZIP/XML: app193 admitted, 449000 RUB, appRating26 raw, unknown withdrawn application number; ETP corporate notification independently associates 193 with Arvectum. Aksay SHA-bound archived derived stats: 55 total/45 admitted, our 119000 RUB/rank38 and winner28400 RUB, but original final DOCX not reverified. Aksioma ETP verified app ordinal3630084; 119000 RUB is *secondary public winner price*, not our bid price, no proven Arvectum rank. Museum Bread final scheduled 2026-10-20, not yet reported. Eight private ETP metadata observations dry-run only, blocked from apply and NOT part of PG77. See [official outcome provenance report](PROCUREMENT_LLM_OFFICIAL_OUTCOMES_2026-10-16.md). Zero train-ready/legal gold.

- [ ] **PROC-LLM-DATA-08 / Verified original EIS final protocols.** Direct getDocsIP ZIP/XML original SHA verified for Aksioma 0187200001726001304 (our company app3630084 admitted, 399000 RUB, appRating6, 17 total / 12 admitted, winner119000) and Aksay 0158300034526000388 (our company app122031738 admitted, 119000 RUB, appRating38, 55 total / 45 admitted, winner28400). Operator email identifies Aksioma company application and RTS notice14.10 identifies Aksay app number with rank38; official original XML establishes price/admission. Original archives in existing ArvectumSSD data/tenders/eis; hashes and QA in [primary EIS source report](PROCUREMENT_LLM_OFFICIAL_EIS_FINAL_PROTOCOLS_2026-10-16.md). Nine metadata events pending PRIVATELY, dry-run only, canonical PG77 unreviewed and gold0.

- [ ] **PROC-LLM-DATA-09 / Post-final EIS event chronology (P0 data quality).** Aksay 0158300034526000388 original EIS final published 14.10 11:26:58 MSK confirms our admitted app122031738 119000 RUB/rating38. Later separate epNoticeApplicationCancel published 11:54:29 MSK concerns a DIFFERENT app122034518, rating14, 57000 RUB in original final. It does not prove procurement-wide cancellation, changed winner or revised company rank. SHA-verified original EIS ZIP plus two XML and fail-closed 9 tests. [Chronology and source receipts](PROCUREMENT_LLM_EIS_EVENT_CHRONOLOGY_2026-10-16.md). Same canonical PG77, nine blocked private ETP events, zero training gold.


**APR-04, 15.10.2026 — isolated owner-identity DEVELOPMENT E2E PASS.** Реквизиты ООО «Арвектум» из двух предоставленных регистрационных документов проверены и использованы только в приватном тестовом профиле; персонализированный анализ сохранённой реальной закупки ЕИС вернул цитируемую НМЦК, но коммерческую квалификацию и пустые owner limits трактует **UNKNOWN**, а не ложным GO. Проверены авторизация, история/версии профиля, синтетический PDF и запрет межклиентского скачивания. [Протокол](../acceptance/APR04_ARVECTUM_COMPANY_ONBOARDING_E2E_2026-10-15.md). **Не закрыто:** передача и проверка оригиналов PDF в операторском кабинете, реальные бизнес-критерии и legal/owner GO; никакого production/платного пилота.

**APR-05, 15.10.2026 — private company tenant/legal-hold DEVELOPMENT E2E PASS.** На новой копии отдельной APR-04 БД проверена привязка профиля ООО «Арвектум» к тестовому SaaS-tenant: операторская авторизация, одноразовое приглашение, повторный invite 410, защищённый профиль без юридического согласия 428, logout/revocation, отсутствие платежей/подписания/юридического согласия. Исходный APR-04 SQLite сохранил прежний SHA-256; 21 APR-05 тест текущего main и 31 тест APR-04/05 совместной ветки PASS. [Изолированный протокол](../acceptance/APR05_OWNER_TENANT_LEGAL_HOLD_E2E_2026-10-15.md). **Не закрыто:** реальные договоры/согласия, публичные тарифы, оплата, запуск SaaS и российский production VPS. Stage изолирован, Owner paid pilot не активирован.

**Приёмка TA ↔ Data Platform, R2/R4/R5 (2026-10-13):** технический рефакторинг Data Platform закрыт; оставшиеся проверки официальной актуальности и допустимого staging R2, независимое human-gold R4 и 20 датированных owner reviews R5 — это открытые ворота **APR-06/07**, а не новый DP core-refactor. Canonical checkpoint: `.agent/checkpoints/TA-DP-ACCEPTANCE-20261013.yaml`; [критерии и доказательства](../acceptance/TA_DP_ACCEPTANCE_HANDOFF_2026-10-13.md). Не путать R5 20 кейсов с более широким APR-06 корпусом 28 кейсов. Продакшен DP, ставки, платные API и watchdog не менять без отдельного разрешения.

### APR-03B — техническая DEVELOPMENT E2E-приёмка: PASS (15.10.2026)

**Принято в изолированном development-контуре:** сохранённый официальный архив 44-ФЗ № 0372200172326000015, оригиналы ЕИС 6/6, локальная Gemma4 12B (4 вызова), проверяемые три цитаты из XML, история/реестр, безопасный экспорт архивной редакции (409). Исправлены ложный предмет закупки, показ расчёта НМЦК как ТКП и пропавшие HTML-цитаты. [Протокол с доказательствами](../acceptance/APR03B_DEVELOPMENT_E2E_RESULT_2026-10-15.md). **Следующий шаг — APR-04 onboarding компании.** Принятие development E2E не закрывает отдельные продакшен, актуальную редакцию ЕИС, платный pilot, юридический GO и другие реальные коммерческие действия.

### Ускоренная E2E-приёмка — решение Owner 15.10.2026

**Для APR-03B DEVELOPMENT E2E разборы ChatGPT считаются экспертными оценками.** Не ждём 20 независимых подписанных human-gold разборов: сначала доказываем реальный путь поиска → оригиналы ЕИС → извлечение → LLM-анализ → цитируемый отчёт → историю/БД → безопасные экспорты. Исправления Owner и юридическая/коммерческая калибровка идут после стабилизации workflow; не разрешены ставки, подпись, платежи и production. До реального успешного end-to-end прогонa APR-03B остаётся OPEN. [Новая приёмка](../acceptance/APR03B_DEVELOPMENT_AI_E2E_POLICY_2026-10-15.md).

### P1/P2 — после P0 или при подтверждённом спросе

- [ ] **APR-08 / ARV-065 — Evidence Copilot (P1).** Только procurement-scoped Q&A/расчёты/объяснения с цитатами; не generic chatbot и не authoritative legal approval.
- [ ] **APR-09 / ARV-023/024/025/026/027 — Supplier → RFQ → TKP (P1, trigger).** Запускать после >=2 платных кейсов, где sourcing/TKP реально является bottleneck; внешняя отправка остаётся HUMAN/REVIEW.
- [ ] **APR-10 / ARV-004 — Feedback Learning Loop (P2, trigger).** Human correction → regression → reviewed candidate → controlled promotion. Не раньше достаточного корпуса (ориентир >=30 useful corrections в >=3 customer/pilot contexts).
- [ ] **PROC-LLM-TRAIN-02 (P2, deferred)** — отдельная будущая Arvectum Procurement LLM (4–12B и LoRA/QLoRA) только после юридически разрешённого curated corpus, реальных human-corrections, frozen independent eval, Owner review. Сейчас **только сбор и provenance**, никакого model training и model promotion.


### Подтверждённый бэклог — ценовая аналитика по реальным протоколам

- [ ] **PRICE-01 / ARV-057 — Конкурентная цена на основе протоколов и себестоимости (P1, Owner-requested, 2026-10-14).** Подключить накопленные результаты определения поставщика к расчёту рекомендуемой ставки Tender Agent. Считать отдельно: (1) прямые внешние затраты, УСН/налоги, комиссию ЭТП и резерв, (2) стоимость собственного труда/полную экономическую себестоимость, (3) распределение реальных допущенных цен по сопоставимым закупкам, НМЦК и число конкурентов, (4) причины отклонений и риск недопуска, (5) стратегический сценарий «первый контракт» с явно заданным пользователем допустимым порогом доходности. Выдавать несколько сценариев (безубыточный/агрессивный/коммерческий) с доказательной базой, источником, датой и предупреждением о малой выборке; **никакого автоматического демпинга и автоподачи без решения человека**. Стартовый реальный кейс: закупка 0158300034526000388, протокол от 14.10.2026; 55 ставок, 45 допущено, 10 отклонено, победитель 28 400 ₽, Arvectum 119 000 ₽ / 38-е место и допуск. Данные импортированы в PostgreSQL tender_bid_result_snapshots / tender_bid_result_offers; копия CSV/JSON: Arvectum/data/tenders/results/0158300034526000388/. **Критерии приёмки:** воспроизводимая загрузка и дедупликация протоколов; сохранение исходных идентификаторов и причин отклонений; фильтрация несопоставимых контрактов; независимый расчёт себестоимости; объяснимое ценовое предложение с диапазоном и ссылками на доказательства; тест на кейсе Аксая с сохранением цены 28 400 ₽ и нашего 38-го места. **Не путать с ARV-069:** вероятностный прогноз победителя и автопромоция моделей остаются deferred до достаточной статистики/frozen benchmark.

### Что сознательно снято с активной продуктовой очереди

- [x] **ARV-066 — One-click procurement import** — завершён в main (9a5a693f).
- [ ] **ARV-069 forecast** — **DEFERRED EXPERIMENT**, а не следующий шаг. Возвращается при >=100 сопоставимых source-bound outcomes и frozen benchmark, показывающем пользу сверх исторического price context.
- [ ] **ARV-028/029 n8n** — только если реально возникнет multi-system orchestration bottleneck.
- [ ] **ARV-047 OpenSearch, ARV-048 ClickHouse, ARV-049 Kubernetes** — только по измеренному capacity/SLO trigger.
- [ ] **B2B-SOURCE-DISCOVERY-2026-10-12 — расширение мониторинга корпоративных IT-закупок (P1, research/read-only).** Цель: находить новые оплачиваемые B2B-заказы, доступные ООО «Арвектум», наряду с 44-ФЗ/223-ФЗ. Кандидаты источников: **Росэлторг (коммерческие процедуры), B2B-Center, Фабрикант, Workspace (digital-тендеры), РТС-тендер (коммерческий/корпоративный сегмент)**. Kwork, FL.ru и другие фриланс-каналы исключены. До интеграции: проверить доступность объявлений, условия участия юридических лиц, тарифы/комиссии, разрешённые способы получения данных, полноту документов и уникальность относительно ЕИС; сформировать 15–20 актуальных релевантных закупок и матрицу источников с GO/NO-GO для каждой интеграции. Реализовать сначала ручной/публичный read-only discovery через существующий intake/дедупликацию без отдельного pipeline. **Эта задача разрешает исследование, но не активирует автоматически ARV-030..037/071 или authenticated ETP connectors**; кодовые интеграции — только после evidence и отдельного решения Owner.
- [ ] **ARV-030..037/071 broad ETP connectors** — только при повторяемом платном customer demand или заметной недоступности целевых закупок через текущие источники.
- [ ] **ARV-046 on-prem, ARV-045 1C/ERP, ARV-070 financing, broader ARV-044 mobile** — customer/contract-triggered.
- [ ] **ARV-062 GitVerse mirror, ARV-075 Mac mini cleanup, ARV-051 dev protocol** — engineering/ops/governance, не product backlog.
- [ ] **ARV-073/074 ID conflicts** — owner/governance reconciliation only.
- [ ] **ARV-067 new vertical ontologies** — только если frozen benchmark показывает устойчивый vertical gap.

## Срез активных чекбоксов — 13.10.2026 (верифицирован по GitHub)

**Смысл статусов.** `MERGED/CI GREEN` — технический результат в репозитории, **не** завершённая бизнес-приёмка. Исторические `ARV/BASE` чекбоксы остаются legacy-регистром и могут повторять APR. Полный счётчик Markdown-чекбоксов включает пересечения и отложенные направления; его нельзя читать как число оставшихся этапов до релиза.

| P0 / ближайшее направление | Технический статус, который удалось подтвердить | Незакрытый gate |
| --- | --- | --- |
| **APR-03 Production Runtime** | PR #251 **MERGED**; локальная Compose/backup/restore подготовка | Российский VPS, боевой TLS/доступ, backup/restore и наблюдаемость в реальной среде. Внешние расходы/production — Owner |
| **APR-03B Operator Workspace** | PR #259 и #260 **MERGED**, локальная проверка оригиналов и CI | **Браузерная приёмка владельца** в /pilot/tender-agent/workspace на реальной закупке (работа с оригиналами, отчёт, цитаты, PDF/DOCX) |
| **APR-04 Onboarding** | PR #252 **MERGED** | Бизнес-проверка профиля ООО «Арвектум», полноты и точности данных, документов, применимости на реальной закупке |
| **APR-05 Paid Pilot / SaaS** | PR #253 **MERGED**, tenant/role/entitlement реализованы в коде; квалификационные PR #407–415 пока **DRAFT и НЕ MERGED** | staging-приёмка изоляции, ролей, легальной обвязки, тарифов и явного Owner-разрешения перед live SaaS/оплатой |
| **APR-06 Commercial Acceptance** | PR #254 и связанные аудиты/квалификация созданы, оригинальные CZN 70/30, 1C 60/40/5/95, RI223 40/60 разобраны; PR #415 `054c5e21` **3/3 GitHub CI SUCCESS**; исходники проверены локально | **20–30 независимых реальных коммерческих кейсов**, оригиналы/изменения ЕИС и точные SHA, человеческие gold-метки, ставки/маржа/квалификация, approved Owner KPI; не объявлять AI-оценку human-gold |
| **APR-07 Quality / SLO** | PR #255 DRAFT, локальные метрики и frozen acceptance snapshots | Независимая человеческая оценка R4, датированные решения владельца R5, достоверные rolling SLO с production/staging, актуальность R2 |
| **B2B corporate sourcing** | PR #399 DRAFT, примерно 10 source-grounded исторических карточек с дедупликацией | 15–20 **актуальных и подходящих** корпоративных IT-закупок, публичные условия участия ООО, тарифы и юридические ограничения; без авторизованных ЭТП-интеграций |
| **P1/P2 / ARV deferred** | APR-08 copilot, APR-09 supplier RFQ/TKP, APR-10 reviewed feedback и прочие ARV/n8n/infra задачи — **не автоматическая P0 очередь** | Фактический клиентский спрос, ≥2 платных sourcing кейса, ≥30 useful corrections / ≥3 customer contexts, либо измеренный capacity/benchmark trigger |

**Дальнейший порядок без дополнительных внешних прав:** (1) безопасно сверить source/CI и статус очереди, (2) подготовить браузерную/юридическую приёмку и независимый APR-06 corpus, (3) собрать качественные текущие B2B источники. Для настоящей браузерной подписи Owner, закупочных заявок, production SaaS и платёжных действий нужно отдельное решение владельца. Один зелёный CI **не** закрывает APR-03/03B/04/05/06/07. Watchdog остаётся в ручном режиме согласно `execution.manual_override=true`.

## Provenance and restoration rule

This roadmap restores the latest canonical Owner backlog snapshot available for recovery: `Arvectum_Backlog_Roadmap_2026-07-30_v9_storage_cleanup.xlsx`, sheet `Полный бэклог`, rows 5–97. The recovered registry is complete for `BASE-001..BASE-018` and `ARV-001..ARV-075` and preserves every historical ID, title, status, priority, dependency, progress value, source and comment without renumbering.

Current repository evidence is recorded as a **reconciliation overlay**. It may confirm, refine or flag a historical item, but it never silently rewrites the 2026-07-30 snapshot. New executable work still requires an explicit entry in `.agent/execution-queue.yaml`; presence here does not grant execution authority.

## Canonical relationship

`master-roadmap.yaml` → complete product scope/history → `.agent/execution-queue.yaml` → admitted executable projection → `.agent/current-task.yaml` → one active checkpoint.

Blocked, REVIEW, OWNER and HUMAN gates remain blocked/gated even when later independent queue work is executable. The roadmap does not expand Company AM-4 authority.

## Owner acceleration directive — 2026-09-14

The Product Owner changes the default development posture from **build-first** to **reuse-first**. Historical ARV IDs/status snapshots below remain immutable history; this directive is a current strategy overlay and does not renumber or silently rewrite them.

**Product thesis:** **Thin Commodity Shell + Deep Decision Core.** Before designing a feature from scratch, first identify who already solved the problem and prefer the shortest lawful path.

| Strategy | Default use | Hard boundary |
|---|---|---|
| `REUSE` | OSS/library/component already solves the commodity problem | Check license, security, maintenance and fit |
| `COPY_PATTERN` | A competitor/public product has a proven UX/workflow/functional pattern | Reimplement behavior; do **not** copy proprietary source, assets, text or private data |
| `ADAPT` | API/protocol/service/standard component can be integrated | Keep vendor boundary replaceable; own only the differentiating layer |
| `INVENT` | Existing options fail or the capability is part of Tender Agent's moat | Requires written gap, differentiation and maintenance-cost justification |

**INVENT gate:** no new custom implementation enters active work until reusable OSS/APIs/public patterns have been checked, the gap is documented, the differentiation maps to Decision Core / Commercial Core / procurement-specific edge cases, and ownership cost is justified. Without that evidence the item defaults to `REUSE`, `COPY_PATTERN` or `ADAPT`.

### Accelerated sequence

| Stage | Priority | Current state | Outcome / evidence |
|---|---|---|---|
| **0. Competitive reverse-spec + reuse registry** | P0 | **done** | PR #56 merged (`8b1c131`): 9 direct products, 10 reuse candidates, active P0/P1 strategy classification and explicit commodity de-scope. |
| **1. Thin commodity shell** | P0 | **done** | Dedicated acceptance matrix proves baseline search/filter + versioned saved profiles + tender card + document download/parsing adapters + auth/visibility + monitoring alerts + export. Focused gate 67 passed / 10 skipped; exact-head CI `37612128040` SUCCESS 9/9; closure PR #192 merged as `a58ec11`. No new commodity subsystem was required. |
| **2. Decision Core v1** | P0 | **done** | Discovery benchmark/hardening PR #59 merged (`762a392`); Decision Core v1 PR #61 merged (`3bf397f`) with evidence-bound fail-closed decisions. |
| **3. Commercial Core** | P0 | **done** | PR #63 merged (`4257cd2`): price-list ingest, tender-to-catalog matching, coverage/cost/headroom and auditable commercial feasibility with HUMAN control. |
| **4. Automation + integrations** | P1 | **done at admitted v1 boundary** | PR #74 (`56ca227`) change monitoring + PR #75 (`fbf6d3c`) ingest resilience + PR #79 (`4149801`) internal integration outbox. External delivery remains disabled and separately gated. |
| **5. Reliability + moat** | P1 | **done at admitted v1 boundary** | PR #76 (`c335c60`) ops observability + PR #77 (`c5e653a`) domain regression registry + PR #80 (`dc87a0b`) read-only 223-ФЗ intake + review-approved PR #81 (`f603c9f`) 223-ФЗ Decision Core. |

### Stage 1 acceptance — 2026-10-07

Stage 1 is now closed at its original exit gate. The accepted commodity journey is:

`authenticated operator → search/filter or versioned saved profile → result/tender card → source document download/parsing adapter → watch/alert feed → report/export`

The closure reuses existing Tender Agent components rather than introducing a new search engine, viewer, auth framework, notification platform, CRM or export stack. Full enterprise IAM/SSO, arbitrary dashboard CRUD, inline PDF.js-style viewing and external notification delivery remain separate future scopes and are not Stage 1 blockers. Acceptance evidence is recorded in `docs/strategy/STAGE1_THIN_COMMODITY_SHELL_ACCEPTANCE.md` and `tests/test_stage1_thin_commodity_shell.py`.

### Commodity default: do not build from scratch

Custom OCR, PDF renderer/viewer, vector/search infrastructure, auth framework, generic chatbot/RAG shell, notification service, analytics/dashboard platform, CRM clone and premature distributed infrastructure are **not** differentiation. Reuse/adapt them unless a measured gap proves otherwise.

### What we deliberately own

Custom engineering is concentrated in: evidence-bound procurement facts; GO/NO-GO and blockers; nomenclature/catalog matching and substitutions; Supplier → RFQ → TKP; real margin/bid economics; contract/procurement risks; 44-ФЗ/223-ФЗ/private edge cases; and the regression corpus built from real failures.

### Strategy success gates

- ≥70% of new P0/P1 **commodity** work resolves through `REUSE` / `COPY_PATTERN` / `ADAPT`.
- 100% of substantive GO/NO-GO claims have source evidence or explicit `Unknown`.
- No hard decision exists without a traceable `document → page → fragment → conclusion` chain.
- Every confirmed real failure/edge case becomes a regression case.
- Competitor reverse-spec is refreshed at milestone boundaries before commodity scope expands.

## Continuous execution directive — 2026-09-15

The Owner requires the single `Tender Agent Watchdog` to be **work-conserving** at the maximum supported cadence: one exact run per hour. A run should do productive work rather than occupy time waiting for CI or another future condition.

The executor must reconcile issue/PR/done-gate state before continuing a stale checkpoint. If a done gate is already satisfied, it must close/reconcile that task rather than start another acceptance loop. Waiting on CI, external acquisition or human review is checkpointed; the lease is released, and another independent admitted `AUTO` item may progress in an isolated branch/checkpoint. A productive run should normally finish/checkpoint within 45 minutes so the next hourly tick is not lost to an overlapping long session. If executable work exists but no valid progress/lease is observed for more than 90 minutes, the next run treats that as a recovery condition and resumes from canonical state immediately.

This changes utilization/cadence only. It does **not** expand AM-4 authority, queue admission, external-action rights, or `REVIEW` / `OWNER` / `HUMAN` gates.

**Historical execution snapshot (2026-09-18):** at that point every explicitly admitted queue item through order 80 was completed and the queue was temporarily exhausted. This paragraph is retained only as history; it is **not** the current executor state.

**Current execution status (2026-10-08, 12:12 MSK):** ARV-066 is merged in main as 9a5a693f, so the essential Commercial Workflow v1 path is complete. ARV-069 is intentionally deferred from immediate execution by the Owner roadmap optimization. The next product task is **APR-01 / ARV-061 — fast cited pre-analysis**. Historical open ARV items are no longer automatic implementation obligations; trigger-backlog items require evidenced triggers.

<!-- CURRENT-CHECKLIST-START -->
## Полная текущая дорожная карта — checklist

> Актуально на **2026-10-08 11:02 MSK**. Чекбокс отражает **current reconciliation overlay**, а не исторический статус из snapshot 2026-07-30. Исторические поля ниже остаются неизменяемыми. `[x]` = текущий scope подтверждён/завершён; незакрытые пункты помечены фактическим gate/status.

### Верхнеуровневые продуктовые стадии

- [x] **Stage 0 — Competitive reverse-spec + reuse registry**
- [x] **Stage 1 — Thin commodity shell**
- [x] **Stage 2 — Decision Core v1**
- [x] **Stage 3 — Commercial Core v1**
- [x] **Stage 4 — Automation + integrations (admitted v1 boundary)**
- [x] **Stage 5 — Reliability + moat (admitted v1 boundary)**
- [x] **Daily Tender Run DTR-1 → DTR-3**
- [x] **iPhone Tender Agent MOB-1 → MOB-4**
- [ ] **Commercial Workflow** — **11/12 технически завершены**; ARV-066 merged в main, ARV-069 — deferred experiment по порогу данных, **не** автоматическое следующее задание.

### Commercial Workflow — текущая исполняемая ветка

- [x] ARV-015 slice — Structured RFQ-first operator profile ingestion
- [x] ARV-019 — Procurement kanban / operator workflow
- [x] ARV-022 — OCR fallback via Data Platform reuse
- [x] ARV-053 — Evidence-backed counterparty cards / risk signals
- [x] ARV-055 — Explainable similar-procurement search
- [x] ARV-057 — Historical price evidence / NMCK range
- [x] ARV-059 — Contract execution / outcome analytics
- [x] ARV-060 — Case discussion / immutable decision journal
- [x] ARV-063 — Review-only application package generator
- [x] ARV-064 — Reusable company document/profile store
- [x] **ARV-066 — One-click procurement import boundary — DONE** (merged main `9a5a693f`; исходный исторический ARV ниже не переписывается)
- [ ] ⏳ **ARV-069 — Competition / bid-price forecast context — DEFERRED** (после ≥100 сопоставимых source-bound outcomes и замороженного benchmark; не следующий P0 шаг)

### Полный canonical legacy registry

#### 0. База проекта

- [x] **BASE-001** — ООО «Арвектум» зарегистрировано, реквизиты и корпоративный контур оформлены — готово · P0
- [x] **BASE-002** — Фирменный стиль, логотип и брендбук — готово · P1
- [x] **BASE-003** — Сайт arvectum.com и базовые digital-каналы — готово · P1
- [x] **BASE-004** — Backend-фундамент: FastAPI, SQLAlchemy, Alembic, Docker, роли и UI — готово · P0
- [x] **BASE-005** — PostgreSQL + pgvector + RAG-контур — готово · P0
- [x] **BASE-006** — Публичный поиск 44-ФЗ и точный поиск по номеру — готово · P0
- [x] **BASE-007** — Рабочий SOAP-контур ЕИС для машиночитаемых данных — готово · P0
- [x] **BASE-008** — Загрузка закупки и формирование отчётов — готово · P0
- [x] **BASE-009** — Извлечение товарных позиций и характеристик — готово · P0
- [x] **BASE-010** — Разделение demo/live и отказ от тихих синтетических fallback — готово · P0
- [x] **BASE-011** — Hermes H1–H4: базовая память, quality gates и feedback — готово · P0
- [x] **BASE-012** — Quality R1–R5: golden loop, provenance и source graph — готово · P0
- [x] **BASE-013** — Демо- и пилотный пакет документов — готово · P1
- [x] **BASE-014** — Базовый личный кабинет: клиенты, проекты и мастер поиска — готово · P1
- [x] **BASE-015** — Стабильный рендер PDF на Linux — готово · P1
- [x] **BASE-016** — R7 controlled pilot baseline: deployment, artifacts, backup/restore и recovery — готово · P0
- [x] **BASE-017** — R8 Customer Pilot Workspace: изолированный клиентский жизненный цикл — готово · P0
- [x] **BASE-018** — R9 Operational Hardening: fail-closed recovery, concurrency и backup/restore — готово · P0

#### 1. Качество ядра

- [x] **ARV-050** — R8: изолированное рабочее пространство клиентского пилота — готово · P0
- [ ] **ARV-073** — R9 Operational Hardening: завершить инженерную отладку и заморозить ядро — ⛔ ID conflict · P0
- [x] **ARV-002** — Стабильный live end-to-end pipeline без скрытых fallback — готово · P0
- [x] **ARV-003** — R10.1: production LLM-анализ с evidence map и confidence — готово · P0
- [x] **ARV-001** — R10.2: Quality & Product Readiness — golden report и release gates — готово · P0
- [ ] **ARV-004** — R10.3: production-loop Hermes и customer-scoped feedback — 🟨 требует revalidation · P0
- [x] **ARV-005** — R10.4: контролируемый пилот на 10–20 реальных закупках — готово · P0
- [ ] **ARV-067** — Вертикальные онтологии и настраиваемые схемы извлечения по категориям — 🟧 REVIEW · P1
- [ ] **ARV-061** — Commercial MVP v1: быстрый cited-преданализ — 🟨 требует revalidation · P1
- [ ] **ARV-065** — Evidence-grounded copilot по закупке: Q&A, AI-юрист и сметчик — 🟨 требует revalidation · P1

#### 2. Источники и production

- [x] **ARV-009** — Оценить объём данных, pgvector и требования к диску — готово · P0
- [x] **ARV-007** — Redis как очередь, lock, cache и rate-limit слой — готово · P0
- [ ] **ARV-075** — Аудит и разгрузка системного диска Mac mini: удалить мусор и перенести данные Арвектум на внешний SSD — 🟨 требует revalidation · P0
- [ ] **ARV-008** — Фоновые задания и workers с прогрессом и повторным запуском — 🟨 требует revalidation · P0
- [x] **ARV-010** — Production-наблюдаемость, безопасность и восстановление — готово · P0
- [ ] **ARV-006** — Добавить полноценную работу с 223-ФЗ — 🟨 остаточный scope · P0
- [ ] **ARV-074** — ODS/Hermes-инфраструктура Mac mini и устранение дублирующихся локальных сервисов — ⛔ ID conflict · P1
- [ ] **ARV-058** — Возобновляемая синхронизация, локальный кэш и идемпотентный импорт — 🟨 требует revalidation · P1
- [ ] **ARV-011** — Выбрать и арендовать VPS для backend — 🔄 в работе · P1
- [ ] **ARV-012** — Переезд с Mac mini на VPS — 🟨 требует revalidation · P1
- [ ] **ARV-013** — Заменить временный CloudPub на нормальный production-доступ — 🟨 требует revalidation · P0
- [ ] **ARV-014** — Белые списки площадок и Anti-DDoS после появления IP VPS — 🟨 требует revalidation · P0

#### 3. Коммерческий MVP

- [x] **ARV-042** — Пилотная программа и критерии успешности — готово · P1
- [x] **ARV-052** — Human-in-the-loop: экспертная проверка и эскалация сложного отчёта — готово · P2
- [ ] **ARV-018** — Commercial MVP v1: карточка GO / NO-GO / NEEDS REVIEW — 🟨 требует revalidation · P1
- [ ] **ARV-020** — Commercial MVP v1: чек-лист готовности заявки — 🟨 требует revalidation · P1
- [ ] **ARV-015** — Профиль поставщика для персонального анализа закупок — 🟨 остаточный scope · P1
- [x] **ARV-064** — Корпоративное хранилище документов и переиспользуемый профиль компании — готово · P1
- [ ] **ARV-016** — Обработка прайс-листов XLSX/CSV/PDF — 🟨 требует revalidation · P1
- [ ] **ARV-017** — Подбор тендеров по прайс-листу и каталогу — 🟨 требует revalidation · P1
- [x] **ARV-053** — Проверка и скоринг контрагентов — готово · P1
- [x] **ARV-019** — Канбан закупок в личном кабинете — готово · P1
- [x] **ARV-063** — Генератор пакета заявки и заполнение клиентских шаблонов — готово · P1
- [ ] **ARV-056** — Тендерный календарь, контроль изменений и наблюдение за заказчиками/конкурентами — 🟨 требует revalidation · P1
- [ ] **ARV-021** — Мониторинг закупок и уведомления — 🟨 требует revalidation · P1
- [x] **ARV-022** — OCR fallback для сканированных документов — готово · P1
- [x] **ARV-060** — Командное обсуждение закупки: чат, упоминания и журнал решений — готово · P2
- [ ] **ARV-066** — Импорт закупки одним кликом: URL, browser extension и share action — 🔄 в работе · P2
- [x] **ARV-055** — Похожие закупки и поиск аналогичных тендеров — готово · P2
- [x] **ARV-057** — Исторические цены, база цен и ориентир НМЦК — готово · P2
- [x] **ARV-059** — Аналитика фактического исполнения контрактов — готово · P2
- [ ] **ARV-069** — Прогноз конкуренции, участников и цены подачи — ⏳ в очереди · P2

#### 9. Управление разработкой

- [ ] **ARV-072** — Регрессионный competitive benchmark на одинаковых реальных закупках — 🔄 в работе · P1
- [ ] **ARV-051** — Протокол параллельной разработки Codex / OpenCode — 🟨 требует revalidation · P0
- [ ] **ARV-062** — Настроить полное зеркало репозитория ai-corporation в GitVerse — 🟨 требует revalidation · P1

#### 4. Go-to-market

- [ ] **ARV-041** — Добить юридическую обвязку SaaS и пилота — 🟧 HUMAN gate · P1
- [ ] **ARV-054** — Прозрачные тарифы, pay-per-analysis и мгновенная демоверсия — 🟨 требует revalidation · P1
- [ ] **ARV-038** — Обновить сайт: продукт вместо общей IT-компании — 🟧 REVIEW · P1
- [ ] **ARV-039** — Метрики сайта и продукта — 🟨 требует revalidation · P1
- [ ] **ARV-040** — Обновить индексацию в Яндексе и Google — 🟨 требует revalidation · P1

#### 7. Масштабирование

- [ ] **ARV-068** — Учёт потребления, квоты, токены и применение тарифных лимитов — 🟨 требует revalidation · P1
- [ ] **ARV-043** — Multi-tenant SaaS: организации, роли и изоляция данных — 🟨 требует revalidation · P2
- [ ] **ARV-046** — Enterprise/on-premise и air-gapped deployment — 🟨 требует revalidation · P2
- [ ] **ARV-045** — Интеграции 1С, CRM, ERP и корпоративных систем — 🟨 требует revalidation · P2
- [ ] **ARV-044** — Web-first + mobile companion «тендерный радар» — 🟨 требует revalidation · P2
- [ ] **ARV-070** — Интеграции банковских гарантий и тендерного финансирования после GO — 🟨 требует revalidation · P3

#### 5. Поставщики и RFQ

- [ ] **ARV-023** — Поиск поставщиков — 🟨 требует revalidation · P1
- [ ] **ARV-024** — База поставщиков и история взаимодействия — 🟨 требует revalidation · P1
- [ ] **ARV-025** — Интеграция почты пользователя: OAuth/SMTP + IMAP/API — 🟨 требует revalidation · P1
- [ ] **ARV-026** — Автоматическая подготовка и рассылка запросов ТКП — 🟨 требует revalidation · P1
- [ ] **ARV-027** — Сравнение ТКП и выбор поставщика — 🟨 требует revalidation · P1
- [ ] **ARV-028** — Развернуть self-hosted n8n как внешний оркестратор — 🟨 требует revalidation · P1
- [ ] **ARV-029** — Первые n8n-пайплайны — 🟨 требует revalidation · P1

#### 6. Коннекторы ЭТП

- [ ] **ARV-030** — Единый слой marketplace connectors — 🟨 остаточный scope · P1
- [ ] **ARV-031** — Дедупликация ЕИС и ЭТП — 🟨 требует revalidation · P1
- [ ] **ARV-032** — Исследовать уникальность данных восьми федеральных ЭТП — 🟨 требует revalidation · P1
- [ ] **ARV-033** — ТЭК-Торг SOAP proof of concept — 🟨 требует revalidation · P1
- [ ] **ARV-036** — Интеграция B2B-Center — 🟨 требует revalidation · P2
- [ ] **ARV-035** — Интеграция Фабрикант — 🟨 требует revalidation · P2
- [ ] **ARV-037** — Интеграция Tender-Pro — 🟨 требует revalidation · P2
- [ ] **ARV-034** — Подключить остальные федеральные ЭТП — 🟨 требует revalidation · P2
- [ ] **ARV-071** — Buyer-side SRM и структурированные ТКП — 🟨 требует revalidation · P2

#### 8. Поздняя оптимизация

- [ ] **ARV-047** — OpenSearch / Elasticsearch для расширенного поиска — 🟨 требует revalidation · P3
- [ ] **ARV-048** — ClickHouse для событий и аналитики — 🟨 требует revalidation · P3
- [ ] **ARV-049** — Kubernetes / Helm — 🟨 требует revalidation · P3

<!-- CURRENT-CHECKLIST-END -->


## Owner product directive — 2026-10-06: Daily Tender Run + iPhone Tender Agent

The Product Owner promotes the real daily procurement workflow observed in production use into the next product layer.

### A. Daily Tender Run — P0

Goal: make the routine workflow reproducible end-to-end with one scheduled/backend run while keeping the substantive bid decision human.

Canonical flow:

EIS search/filter → dedupe → shortlist → document acquisition on Mac mini → Data Platform → deep analysis → evidence-bound summary → manager inbox → HUMAN GO / NO GO / DEFER → application readiness → submission tracking → outcome → postmortem → portfolio metrics.

Required behavior:

- saved filters on a configurable schedule plus manual rerun;
- deduplicate already-seen procurements and reprocess only material changes;
- cheap screening before expensive deep analysis;
- EIS documents acquired through Mac mini and analyzed locally via Data Platform;
- one manager digest plus one evidence-grounded report per shortlisted procurement;
- agent recommendation, rationale, confidence, blockers and evidence persisted separately from the human decision;
- GO / NO GO / DEFER is the explicit manager gate;
- after GO, prepare readiness artifacts automatically without fabricating submission/signature success;
- capture factual submission, platform, price, timestamps, outcome, winning price/participant and postmortem cause when evidence exists;
- write stages into the canonical event/decision/outcome lifecycle and Procurement Portfolio.

Success gate: a normal business day can be processed without chat-driven orchestration; the manager only reviews prepared summaries and records a decision.

This reuses existing search, intake, Data Platform, screening, decision log, submission control, outcome intake, postmortem and Procurement Portfolio capabilities. It is not a parallel data model.

### B. ARV-044 mobile companion — promoted to P0 owner priority

Historical ARV-044 remains immutable in the recovered snapshot. The Owner now promotes its current product meaning from a deferred lightweight “tender radar” into the primary iPhone decision client for Tender Agent.

MVP contract:

- native SwiftUI iPhone app;
- Mac mini remains the Tender Agent backend;
- private backend access through Tailscale for the internal MVP;
- APNs push for new reports, deferred-due items, material procurement changes, deadline risk and published outcomes;
- inbox/digest with manager-ready summaries;
- procurement card with NMCK, deadline, recommendation, blockers, risks, unknowns and evidence;
- explicit GO / NO GO / DEFER actions with optional reason/comment;
- mobile Portfolio for decisions, submissions and outcomes;
- deep links to EIS/full web report;
- mobile decisions written to the same canonical decision log as web decisions.

Human boundary:

- the app may present the agent recommendation but never turns it into a bid decision automatically;
- ETP/EDS/signature actions remain explicit human steps where required;
- submission/result states are recorded only from real evidence or explicit human confirmation.

Detailed spec: docs/product/Daily_Tender_Run_and_iPhone_MVP.md.

**Current product status (2026-10-07):** **MOB-4 is completed and merged** in PR #183 as `bdcd868f1c42f3d3165cc8cad2c83b63b682521b`; exact-head CI run `37584606448` passed all 9 jobs. The iPhone Portfolio now consumes the canonical Procurement Portfolio projection for decision/submission/outcome totals and rates, provides deterministic pipeline/outcome filters, shows grounded submission/outcome timestamps and rationale/postmortem data, and refreshes canonical state before opening a deep-linked case. Missing evidence remains pending/unknown. **DTR-3** remains completed in PR #180 (`3b25e10`) and preserves the same HUMAN/source-evidence gates. No new mobile stage is admitted by this reconciliation.

### Delivery sequence

| Stage | Priority | Deliverable | Exit condition |
|---|---|---|---|
| DTR-1 | P0 | **DONE — Daily Tender Run domain/orchestrator + persisted state** | Pre-decision contour remains implemented and restartable |
| DTR-2 | P0 | **DONE — manager inbox/digest API + mobile façade** | Pre-decision manager-attention contour remains implemented |
| MOB-1 | P0 | **DONE — SwiftUI read-only inbox + procurement summary** | PR #171 merged; iPhone securely reads live Mac mini reports |
| MOB-2 | P0 | **DONE — GO / NO GO / DEFER API + mobile actions** | PR #173 merged; human mobile decisions are audited and visible in Procurement Portfolio |
| MOB-3 | P0 | **DONE — APNs push + deep links** | PR #176 merged; bounded push/deep-link routing opens the correct Tender Agent case |
| DTR-3 | P1 | **DONE — post-GO readiness + submission/result monitoring** | PR #180 merged; only HUMAN/source-grounded evidence advances readiness, submission and outcome state |
| MOB-4 | P1 | **DONE — mobile portfolio/metrics polish** | PR #183 merged; canonical pipeline/outcomes and factual rates are comfortable to review from phone |

Roadmap status is now reconciled to execution: MOB-1, MOB-2, MOB-3, DTR-3 and MOB-4 were separately admitted, completed, and merged. This closes the currently defined bounded iPhone delivery sequence; this roadmap update does **not** admit a new development item.

### DOCUMENT-QA-005 reconciliation

`DOCUMENT-QA-005` is **done**: issue #16 had already met its unbiased strict `customer_name` acceptance gate and was closed `completed` before the later #52 calibration. Case #52 is retained as post-acceptance regression evidence. Its generic EIS placement-organization/customer defect was fixed by PR #54 and issue #53 is completed; this does not silently reopen #16 or authorize an endless sequence of fresh blind cases.

## Current reconciliation highlights

- **BASE-001..BASE-018:** current reconciliation is **18/18 confirmed_done**. This is a current evidence overlay only; the historical 2026-07-30 percentages and statuses remain unchanged. BASE-011 is closed as the Hermes infrastructure foundation, while real-user self-improvement is retained under ARV-004 as a post-MVP, not-admitted Feedback & Learning Loop.
- **Current queue — 2026-10-08:** COMMERCIAL-WORKFLOW is **10/12 complete**. ARV-064 is merged in PR #217 (`75beab91`); ARV-066 is the active item on `agent/commercial-workflow-arv-066-001`; ARV-069 remains ready behind it. AM-4 is at **6/10** after PR #217. Consequential external actions and Product/HUMAN/REVIEW gates remain fail-closed.
- **ARV-044 — mobile companion:** current Owner priority is P0; MOB-1 is complete in PR #171 (`01b4be72`), MOB-2 in PR #173 (`fe92b39`), MOB-3 in PR #176 (`3ab3872`), and MOB-4 in PR #183 (`bdcd868`). DTR-3 post-GO orchestration is also complete in PR #180 (`3b25e10`) and preserves the same HUMAN participation boundary. The currently defined native-iPhone MVP sequence is implemented; Android, public multi-tenant release and autonomous decision/submission remain deferred and are not implied complete. Historical 2026-07-30 P2/5% fields remain unchanged in the immutable snapshot.
- **ARV-001 — quality/product readiness:** current git history records the later governed closure; the July snapshot remains preserved underneath the overlay.
- **ARV-003 — production LLM analysis:** current docs refer to an accepted ARV-003 bundle, while an older R10.1 backlog status still says Gate 5 ready. This inconsistency is preserved as a status-revalidation item rather than silently resolved.
- **ARV-041 — legal SaaS/pilot package:** repository package exists, but the canonical legal release gate remains human: director approval, qualified Russian counsel review and infrastructure/Roskomnadzor/localization/retention checks.
- **ARV-067 — vertical ontologies / electrical equipment knowledge:** electrical ontology assets, taxonomy/profiles/truth packs and gated shadow work are present; current repository tests explicitly keep the ontology out of production runtime. Expert acceptance/evidence remains a gate.
- **ARV-006 — full 223-ФЗ:** the bounded v1 intake and evidence-bound decision increments are now completed (PR #80 + #81). This advances ARV-006 materially but does not silently claim every historical meaning of “full 223-ФЗ support” is finished; residual breadth remains a future scope decision.
- **ARV-017 / ARV-023:** restored with their actual historical meanings: ARV-017 is tender matching against price lists/catalogs; ARV-023 is supplier search.
- **ARV-010 / ARV-021 / ARV-025 / ARV-029 / ARV-031 / ARV-045 / ARV-056 / ARV-058 / ARV-072:** bounded v1 infrastructure has now landed through PRs #74–#77 and #79. Historical broader meanings remain immutable; the reconciliation overlay records implemented foundations without claiming unbuilt external transports, full connector breadth, or later analytics are complete.
- **ARV-073 / ARV-074:** later documents reused these IDs for different work. The conflict is recorded fail-closed; no renumbering or silent reassignment was performed.
- **ARV-076 / ARV-096:** observed after the 2026-07-30 snapshot. They are recorded separately and are not used to invent missing IDs or automatic queue admission.

## Current executor programs

The accelerated admitted pipeline that was active on 2026-09-15 is now fully reconciled as completed.

| Program | State | Source / completion evidence |
|---|---|---|
| `REUSE-FIRST-001` | **done** | PR #56 merged as `8b1c131`; 9-product reverse-spec + 10-candidate reuse registry |
| `BENCHMARK-PIPELINE-001` | done | issue #1 |
| `DOCUMENT-QA-004` | done | issue #11 |
| `DOCUMENT-QA-005` | **done** | issue #16 accepted/closed; #52/#53 post-acceptance hardening; PR #54 |
| `BUILD-DOCKER-CONTEXT-001` | **done** | issue #19; PR #58 merged as `8924a857` |
| `DISCOVERY-QA-001` | **done** | issue #2; PR #59 merged as `762a392` |
| `DECISION-CORE-V1-001` | **done** | issue #60; PR #61 merged as `3bf397f` |
| `COMMERCIAL-CORE-V1-001` | **done** | issue #62; PR #63 merged as `4257cd2` |
| `DOCUMENT-QA-NEXT-INCREMENT` | **done** | issue #51; PR #73 merged as `dca11d4` |
| `CHANGE-MONITORING-V1-001` | **done** | issue #65; PR #74 merged as `56ca227` |
| `INGEST-RESILIENCE-V1-001` | **done** | issue #66; PR #75 merged as `fbf6d3c` |
| `INTEGRATION-OUTBOX-V1-001` | **done** | issue #67; PR #79 merged as `4149801` |
| `OPS-OBSERVABILITY-V1-001` | **done** | issue #68; PR #76 merged as `c335c60` |
| `223FZ-INGEST-V1-001` | **done** | issue #69; PR #80 merged as `dc87a0b` |
| `223FZ-DECISION-V1-001` | **done** | issue #70; PR #81 merged as `f603c9f` after explicit Product Owner approval |
| `DOMAIN-REGRESSION-V1-001` | **done** | issue #71; PR #77 merged as `c5e653a` |
| `MOB-1-IOS-INBOX-001` | **done** | ARV-044 P0 slice; PR #171 merged as `01b4be72`; exact-head CI `37518592972` SUCCESS |
| `MOB-2-IOS-DECISIONS-001` | **done** | ARV-044 P0 slice; PR #173 merged as `fe92b39`; exact-head CI `37524387682` SUCCESS |
| `MOB-3-IOS-PUSH-DEEPLINKS-001` | **done** | ARV-044 P0 slice; PR #176 merged as `3ab3872`; exact-head CI `37533637202` SUCCESS; physical APNs delivery still requires Apple push entitlement/credentials |
| `DTR-3-POST-GO-AUTOMATION-001` | **done** | Daily Tender Run post-GO slice; PR #180 merged as `3b25e10`; exact-head CI `37575956723` SUCCESS 9/9; readiness/submission/outcome advancement remains HUMAN/source-evidence gated |
| `MOB-4-IOS-PORTFOLIO-METRICS-001` | **done** | ARV-044 P1 polish; PR #183 merged as `bdcd868`; exact-head CI `37584606448` SUCCESS 9/9; canonical portfolio metrics/outcomes only, no new consequential action |

### Execution queue after reconciliation

As of **2026-10-08 11:02 MSK**, the Owner-admitted Commercial Workflow is **10/12 complete**. The merged completion chain now includes ARV-022 through ARV-064; **COMMERCIAL-WORKFLOW-ARV-066-001** is actively executing on its isolated branch and **COMMERCIAL-WORKFLOW-ARV-069-001** remains the final ready item. The queue is therefore **not empty**. BASE-001..BASE-018 remain 18/18 confirmed_done, and the separate ARV-004 Feedback & Learning Loop remains post-MVP/not admitted. Human usefulness/commercial acceptance and all consequential-action gates remain HUMAN/REVIEW where defined.


### Available continuation branches — candidate matrix

These are **roadmap branches, not admitted work**. Selecting one means creating a bounded task/Definition of Done and explicitly admitting it to the execution queue. The historical IDs listed here are preserved; this matrix does not create new ARV IDs.

| Branch | Historical scope | What remains useful to do | Main gate |
|---|---|---|---|
| **CORE-QUALITY-PILOT** | ARV-002, 003, 004, 005, 061, 065, 067 | Revalidate live E2E/LLM readiness; finish Hermes/customer feedback loop; controlled 10–20 procurement pilot; fast cited pre-analysis; evidence-grounded copilot; ontology acceptance | Pilot/customer evidence and ARV-067 expert acceptance are REVIEW/HUMAN |
| **PRODUCTION-RUNTIME** | ARV-008, 010, 011–014, 075 | Workers/jobs; residual security/recovery after observability v1; VPS/production access/migration/allowlists; Mac storage revalidation | Production/network/provider/local destructive changes require explicit applicable authority |
| **COMMERCIAL-WORKFLOW** | ARV-015, 019, 022, 053, 055, 057, 059, 060, 063, 064, 066, 069 | Supplier profile; kanban; reusable OCR fallback; counterparty checks; company docs; application package; collaboration/import; later analytics | No automated participation decision, legal acceptance or application submission |
| **SUPPLIER-RFQ** | ARV-023–029 | Supplier search/database; user-mail adapter; RFQ/TKP preparation/comparison; n8n orchestration | External supplier/customer email/RFQ send remains REVIEW/HUMAN |
| **ETP-CONNECTORS** | ARV-030–037, 071 | Unified marketplace connector layer; federal ETP uniqueness research; TEK-Torg/Fabrikant/B2B-Center/Tender-Pro/other ETPs | Read-only acquisition can be bounded; authenticated/consequential platform actions need separate authority |
| **223FZ-BREADTH** | ARV-006 | Expand beyond completed read-only intake + Decision Core v1 using measured source/procedure gaps | New breadth needs concrete regression/corpus evidence; unsupported legal/procedural claims remain UNKNOWN/NEEDS_REVIEW |
| **MONITORING-DELIVERY** | ARV-021, 056, 025, 029, 045 | Extend completed internal monitoring/outbox foundation to approved email/CRM/webhook/scheduled-reporting adapters | Live external delivery remains disabled until separate REVIEW/HUMAN authority |
| **COMPETITIVE-BENCHMARK** | ARV-072 | Use completed domain-regression infrastructure for identical-procurement competitor benchmark refresh | Corpus/method frozen before outputs; anti-circularity mandatory |
| **GO-TO-MARKET** | ARV-038–041, 054 | Product-first site; metrics; indexing; tariffs/demo; legal SaaS/pilot package | ARV-041 remains director/counsel/regulatory HUMAN gate; pricing/public commitments need Owner approval |
| **SAAS-SCALE** | ARV-043–046, 068, 070 | Multi-tenant orgs/roles/isolation; quotas; on-prem/air-gapped; mobile expansion beyond the completed internal iPhone MVP (for example public/multi-tenant or Android); later finance/integration | Financing/guarantees/external enterprise commitments are HUMAN/commercial gates |
| **DEVELOPMENT-GOVERNANCE** | ARV-051, 062 | Revalidate parallel-development protocol; mirror posture; reusable Project Watchdog binding | Must not alter Company/Product authority; open PR #78 is maintenance only |
| **LATE-INFRA** | ARV-047–049 | OpenSearch, ClickHouse, Kubernetes/Helm when measured need appears | Deferred + reuse-first measured-gap gate |
| **STATUS-REVALIDATION** | BASE-003, 007, 011, 012, 014; ARV-003, 051, 075 | Reconcile stale July progress/status values against current repository/runtime evidence | Status reconciliation only; no implementation authority |
| **ID-CONFLICT-RESOLUTION** | ARV-073, ARV-074 | Resolve later ID reuse versus preserved historical meanings without silent renumbering | Explicit OWNER reconciliation required |

The already delivered Decision Core, Commercial Core, monitoring, ingest resilience, integration outbox, observability, 223-ФЗ v1 and domain-regression foundations should **not** be reopened as generic continuation branches without a concrete regression or an explicitly new bounded increment.


## ID conflicts

| ID | Historical canonical meaning | Later reuse | Resolution |
|---|---|---|---|
| `ARV-073` | R9 Operational Hardening: завершить инженерную отладку и заморозить ядро | ODS local AI infrastructure in docs/product/Product_Backlog.md | unresolved; historical meaning preserved, later reuse is not admitted under this ID automatically |
| `ARV-074` | ODS/Hermes-инфраструктура Mac mini и устранение дублирующихся локальных сервисов | Obsidian Mind memory pilot in docs/product/Product_Backlog.md | unresolved; historical meaning preserved, later reuse is not admitted under this ID automatically |

## Complete recovered roadmap

The table below is a compact view grouped by product block. The machine-readable YAML is authoritative for the full historical fields, normalized dependencies, original dependency surface and evidence overlay.

### 0. База проекта

| ID | Queue | Historical status | Priority | Progress | Task | Current reconciliation |
|---|---:|---|---|---:|---|---|
| `BASE-001` | 0 | Готово | P0 | 100% | ООО «Арвектум» зарегистрировано, реквизиты и корпоративный контур оформлены | confirmed_done |
| `BASE-002` | 0 | Готово | P1 | 100% | Фирменный стиль, логотип и брендбук | confirmed_done |
| `BASE-003` | 0 | Базовый контур готов | P1 | 75% | Сайт arvectum.com и базовые digital-каналы | confirmed_done |
| `BASE-004` | 0 | Готово | P0 | 100% | Backend-фундамент: FastAPI, SQLAlchemy, Alembic, Docker, роли и UI | confirmed_done |
| `BASE-005` | 0 | Готово | P0 | 100% | PostgreSQL + pgvector + RAG-контур | confirmed_done |
| `BASE-006` | 0 | Готово | P0 | 100% | Публичный поиск 44-ФЗ и точный поиск по номеру | confirmed_done |
| `BASE-007` | 0 | Базовый контур готов | P0 | 85% | Рабочий SOAP-контур ЕИС для машиночитаемых данных | confirmed_done |
| `BASE-008` | 0 | Готово | P0 | 100% | Загрузка закупки и формирование отчётов | confirmed_done |
| `BASE-009` | 0 | Готово | P0 | 100% | Извлечение товарных позиций и характеристик | confirmed_done |
| `BASE-010` | 0 | Готово | P0 | 100% | Разделение demo/live и отказ от тихих синтетических fallback | confirmed_done |
| `BASE-011` | 0 | Базовый контур готов | P0 | 70% | Hermes H1–H4: базовая память, quality gates и feedback | confirmed_done |
| `BASE-012` | 0 | Базовый контур готов | P0 | 80% | Quality R1–R5: golden loop, provenance и source graph | confirmed_done |
| `BASE-013` | 0 | Готово | P1 | 100% | Демо- и пилотный пакет документов | confirmed_done |
| `BASE-014` | 0 | Базовый контур готов | P1 | 65% | Базовый личный кабинет: клиенты, проекты и мастер поиска | confirmed_done |
| `BASE-015` | 0 | Готово | P1 | 100% | Стабильный рендер PDF на Linux | confirmed_done |
| `BASE-016` | 0 | Готово | P0 | 100% | R7 controlled pilot baseline: deployment, artifacts, backup/restore и recovery | confirmed_done |
| `BASE-017` | 0 | Готово | P0 | 100% | R8 Customer Pilot Workspace: изолированный клиентский жизненный цикл | confirmed_done |
| `BASE-018` | 0 | Готово | P0 | 100% | R9 Operational Hardening: fail-closed recovery, concurrency и backup/restore | confirmed_done |

### 1. Качество ядра

| ID | Queue | Historical status | Priority | Progress | Task | Current reconciliation |
|---|---:|---|---|---:|---|---|
| `ARV-050` | 0 | Готово | P0 | 100% | R8: изолированное рабочее пространство клиентского пилота | confirmed_done |
| `ARV-073` | 0 | Готово | P0 | 100% | R9 Operational Hardening: завершить инженерную отладку и заморозить ядро | id_conflict |
| `ARV-002` | 0 | Базовый контур готов | P0 | 90% | Стабильный live end-to-end pipeline без скрытых fallback | confirmed_done |
| `ARV-003` | 2 | В работе | P0 | 97% | R10.1: production LLM-анализ с evidence map и confidence | accepted_evidence_present_needs_status_revalidation |
| `ARV-001` | 3 | Запланировано | P0 | 85% | R10.2: Quality & Product Readiness — golden report и release gates | completed_governed |
| `ARV-004` | 4 | Запланировано | P0 | 66% | R10.3: production-loop Hermes и customer-scoped feedback | needs_revalidation — post-MVP, not admitted |
| `ARV-005` | 5 | Запланировано | P0 | 45% | R10.4: контролируемый пилот на 10–20 реальных закупках | confirmed_done |
| `ARV-067` | 7 | На проверке | P1 | 90% | Вертикальные онтологии и настраиваемые схемы извлечения по категориям | review |
| `ARV-061` | 12 | Запланировано | P1 | 5% | Commercial MVP v1: быстрый cited-преданализ | needs_revalidation |
| `ARV-065` | 37 | Запланировано | P1 | 0% | Evidence-grounded copilot по закупке: Q&A, AI-юрист и сметчик | needs_revalidation |

### 2. Источники и production

| ID | Queue | Historical status | Priority | Progress | Task | Current reconciliation |
|---|---:|---|---|---:|---|---|
| `ARV-009` | 0 | Готово | P0 | 100% | Оценить объём данных, pgvector и требования к диску | confirmed_done |
| `ARV-007` | 0 | Готово | P0 | 100% | Redis как очередь, lock, cache и rate-limit слой | confirmed_done |
| `ARV-075` | 1 | Запланировано | P0 | 0% | Аудит и разгрузка системного диска Mac mini: удалить мусор и перенести данные Арвектум на внешний SSD | needs_revalidation |
| `ARV-008` | 6 | Запланировано | P0 | 25% | Фоновые задания и workers с прогрессом и повторным запуском | needs_revalidation |
| `ARV-010` | 9 | В работе | P0 | 93% | Production-наблюдаемость, безопасность и восстановление | confirmed_done |
| `ARV-006` | 15 | Запланировано | P0 | 10% | Добавить полноценную работу с 223-ФЗ | needs_revalidation |
| `ARV-074` | 16 | Исследование | P1 | 5% | ODS/Hermes-инфраструктура Mac mini и устранение дублирующихся локальных сервисов | id_conflict |
| `ARV-058` | 17 | Запланировано | P1 | 10% | Возобновляемая синхронизация, локальный кэш и идемпотентный импорт | needs_revalidation |
| `ARV-011` | 18 | В работе | P1 | 55% | Выбрать и арендовать VPS для backend | in_progress |
| `ARV-012` | 19 | Запланировано | P1 | 25% | Переезд с Mac mini на VPS | needs_revalidation |
| `ARV-013` | 20 | Запланировано | P0 | 0% | Заменить временный CloudPub на нормальный production-доступ | needs_revalidation |
| `ARV-014` | 21 | Запланировано | P0 | 28% | Белые списки площадок и Anti-DDoS после появления IP VPS | needs_revalidation |

### 3. Коммерческий MVP

| ID | Queue | Historical status | Priority | Progress | Task | Current reconciliation |
|---|---:|---|---|---:|---|---|
| `ARV-042` | 0 | Готово | P1 | 100% | Пилотная программа и критерии успешности | confirmed_done |
| `ARV-052` | 0 | Готово | P2 | 100% | Human-in-the-loop: экспертная проверка и эскалация сложного отчёта | confirmed_done |
| `ARV-018` | 13 | В работе | P1 | 60% | Commercial MVP v1: карточка GO / NO-GO / NEEDS REVIEW | needs_revalidation |
| `ARV-020` | 14 | Запланировано | P1 | 20% | Commercial MVP v1: чек-лист готовности заявки | needs_revalidation |
| `ARV-015` | 22 | В работе | P1 | 45% | Профиль поставщика для персонального анализа закупок | revalidated_residual_gap |
| `ARV-064` | 23 | Запланировано | P1 | 0% | Корпоративное хранилище документов и переиспользуемый профиль компании | needs_revalidation |
| `ARV-016` | 24 | Запланировано | P1 | 5% | Обработка прайс-листов XLSX/CSV/PDF | needs_revalidation |
| `ARV-017` | 25 | Запланировано | P1 | 0% | Подбор тендеров по прайс-листу и каталогу | needs_revalidation |
| `ARV-053` | 26 | Запланировано | P1 | 0% | Проверка и скоринг контрагентов | needs_revalidation |
| `ARV-019` | 27 | Запланировано | P1 | 10% | Канбан закупок в личном кабинете | needs_revalidation |
| `ARV-063` | 28 | Запланировано | P1 | 0% | Генератор пакета заявки и заполнение клиентских шаблонов | needs_revalidation |
| `ARV-056` | 29 | Запланировано | P1 | 0% | Тендерный календарь, контроль изменений и наблюдение за заказчиками/конкурентами | needs_revalidation |
| `ARV-021` | 30 | Запланировано | P1 | 10% | Мониторинг закупок и уведомления | needs_revalidation |
| `ARV-022` | 36 | Запланировано | P1 | 5% | OCR fallback для сканированных документов | needs_revalidation |
| `ARV-060` | 43 | Запланировано | P2 | 0% | Командное обсуждение закупки: чат, упоминания и журнал решений | needs_revalidation |
| `ARV-066` | 44 | Запланировано | P2 | 0% | Импорт закупки одним кликом: URL, browser extension и share action | needs_revalidation |
| `ARV-055` | 45 | Запланировано | P2 | 0% | Похожие закупки и поиск аналогичных тендеров | needs_revalidation |
| `ARV-057` | 46 | Исследование | P2 | 0% | Исторические цены, база цен и ориентир НМЦК | needs_revalidation |
| `ARV-059` | 47 | Исследование | P2 | 0% | Аналитика фактического исполнения контрактов | needs_revalidation |
| `ARV-069` | 48 | Исследование | P2 | 0% | Прогноз конкуренции, участников и цены подачи | needs_revalidation |

### 4. Go-to-market

| ID | Queue | Historical status | Priority | Progress | Task | Current reconciliation |
|---|---:|---|---|---:|---|---|
| `ARV-041` | 11 | На проверке | P1 | 95% | Добить юридическую обвязку SaaS и пилота | human_gate |
| `ARV-054` | 31 | Запланировано | P1 | 5% | Прозрачные тарифы, pay-per-analysis и мгновенная демоверсия | needs_revalidation |
| `ARV-038` | 33 | В работе | P1 | 45% | Обновить сайт: продукт вместо общей IT-компании | review |
| `ARV-039` | 34 | Запланировано | P1 | 20% | Метрики сайта и продукта | needs_revalidation |
| `ARV-040` | 35 | Запланировано | P1 | 10% | Обновить индексацию в Яндексе и Google | needs_revalidation |

### 5. Поставщики и RFQ

| ID | Queue | Historical status | Priority | Progress | Task | Current reconciliation |
|---|---:|---|---|---:|---|---|
| `ARV-023` | 38 | Запланировано | P1 | 0% | Поиск поставщиков | needs_revalidation |
| `ARV-024` | 39 | Запланировано | P1 | 0% | База поставщиков и история взаимодействия | needs_revalidation |
| `ARV-025` | 40 | Запланировано | P1 | 0% | Интеграция почты пользователя: OAuth/SMTP + IMAP/API | needs_revalidation |
| `ARV-026` | 41 | В работе | P1 | 30% | Автоматическая подготовка и рассылка запросов ТКП | needs_revalidation |
| `ARV-027` | 42 | Запланировано | P1 | 20% | Сравнение ТКП и выбор поставщика | needs_revalidation |
| `ARV-028` | 49 | Запланировано | P1 | 5% | Развернуть self-hosted n8n как внешний оркестратор | needs_revalidation |
| `ARV-029` | 50 | Запланировано | P1 | 0% | Первые n8n-пайплайны | needs_revalidation |

### 6. Коннекторы ЭТП

| ID | Queue | Historical status | Priority | Progress | Task | Current reconciliation |
|---|---:|---|---|---:|---|---|
| `ARV-030` | 51 | В работе | P1 | 35% | Единый слой marketplace connectors | needs_revalidation |
| `ARV-031` | 52 | Запланировано | P1 | 0% | Дедупликация ЕИС и ЭТП | needs_revalidation |
| `ARV-032` | 53 | Исследование | P1 | 10% | Исследовать уникальность данных восьми федеральных ЭТП | needs_revalidation |
| `ARV-033` | 54 | Исследование | P1 | 20% | ТЭК-Торг SOAP proof of concept | needs_revalidation |
| `ARV-036` | 55 | Исследование | P2 | 0% | Интеграция B2B-Center | needs_revalidation |
| `ARV-035` | 56 | Исследование | P2 | 0% | Интеграция Фабрикант | needs_revalidation |
| `ARV-037` | 57 | Исследование | P2 | 0% | Интеграция Tender-Pro | needs_revalidation |
| `ARV-034` | 58 | Запланировано | P2 | 0% | Подключить остальные федеральные ЭТП | needs_revalidation |
| `ARV-071` | 59 | Исследование | P2 | 0% | Buyer-side SRM и структурированные ТКП | needs_revalidation |

### 7. Масштабирование

| ID | Queue | Historical status | Priority | Progress | Task | Current reconciliation |
|---|---:|---|---|---:|---|---|
| `ARV-068` | 32 | Запланировано | P1 | 0% | Учёт потребления, квоты, токены и применение тарифных лимитов | needs_revalidation |
| `ARV-043` | 60 | В работе | P2 | 68% | Multi-tenant SaaS: организации, роли и изоляция данных | needs_revalidation |
| `ARV-046` | 61 | Исследование | P2 | 20% | Enterprise/on-premise и air-gapped deployment | needs_revalidation |
| `ARV-045` | 62 | Отложено | P2 | 0% | Интеграции 1С, CRM, ERP и корпоративных систем | needs_revalidation |
| `ARV-044` | 63 | Отложено | P2 | 5% | Web-first + mobile companion «тендерный радар» | needs_revalidation |
| `ARV-070` | 64 | Отложено | P3 | 0% | Интеграции банковских гарантий и тендерного финансирования после GO | needs_revalidation |

### 8. Поздняя оптимизация

| ID | Queue | Historical status | Priority | Progress | Task | Current reconciliation |
|---|---:|---|---|---:|---|---|
| `ARV-047` | 66 | Отложено | P3 | 0% | OpenSearch / Elasticsearch для расширенного поиска | needs_revalidation |
| `ARV-048` | 67 | Отложено | P3 | 0% | ClickHouse для событий и аналитики | needs_revalidation |
| `ARV-049` | 68 | Отложено | P3 | 0% | Kubernetes / Helm | needs_revalidation |

### 9. Управление разработкой

| ID | Queue | Historical status | Priority | Progress | Task | Current reconciliation |
|---|---:|---|---|---:|---|---|
| `ARV-072` | 8 | В работе | P1 | 35% | Регрессионный competitive benchmark на одинаковых реальных закупках | in_progress |
| `ARV-051` | 10 | Базовый контур готов | P0 | 98% | Протокол параллельной разработки Codex / OpenCode | needs_revalidation |
| `ARV-062` | 65 | Запланировано | P1 | 0% | Настроить полное зеркало репозитория ai-corporation в GitVerse | needs_revalidation |

## Post-snapshot observed IDs

| ID | Work | State | Admission |
|---|---|---|---|
| `ARV-076` | Docker/Colima backup and restore | implementation_present_acceptance_followup | not inferred into execution queue |
| `ARV-096` | Real EIS document-set acceptance | observed_post_snapshot_work | not inferred into execution queue; gaps ARV-077..ARV-095 are not invented |

## Continuous Owner-directed continuation

`OWNER-CONTINUOUS-ROADMAP-2026-09-18` keeps the hourly executor work-conserving when the admitted queue becomes empty. Selection is deterministic from the continuation matrix in document order, one bounded item per run. Existing bounded tasks are preferred; otherwise only an evidence/revalidation slice may be materialized. This does **not** authorize product-priority invention, new material architecture, authority downgrades, production/external effects, or bypass of REVIEW/HUMAN/OWNER gates.

The first materialized continuation slice is `ARV-002-REVALIDATION-001` under `CORE-QUALITY-PILOT`. The 2026-09-18 watchdog policy change is material for Company AM-4 review purposes, so future automatic merges fail closed to REVIEW until attributable Owner renewal; implementation/testing/review-ready PR preparation may continue.

## ARV-002 revalidation — 2026-09-19

Current exact-number public EIS lookup is live and the source-to-handoff/source-graph/recovery regressions are green. The revalidation did **not** mark ARV-002 fully done: the current EIS search-card parser can populate `customer_name` with page JavaScript via an overly broad fallback, while the stricter common-info detail extractor returns the correct explicit customer.

Evidence and the single bounded, non-admitted successor candidate `ARV-002-LIVE-CUSTOMER-PARSE-001` are recorded in `docs/roadmap/ARV-002_REVALIDATION_2026-09-19.md` and the ARV-002 reconciliation overlay. No implementation authority is inferred from candidate status.

### ARV-002 residual closure — 2026-10-07

The Owner explicitly admitted ARV-002-LIVE-CUSTOMER-PARSE-001. The raw-HTML customer regex fallback was removed, a deterministic JavaScript-pollution regression fixture was added, and search cards now fail closed to customer_name=null unless explicit customer-scoped evidence exists. The common-info detail extractor remains authoritative.

Verification: 87 focused live-path/parser/source-graph/no-fallback tests passed; the companion persistence/recovery gate passed 32 tests with 12 environment/profile skips; make check passed; and a read-only exact-number EIS run for 0888500000226000399 returned a clean fail-closed search card plus the correct explicit detail-page customer. Evidence is in docs/roadmap/ARV-002_LIVE_CUSTOMER_PARSE_2026-10-07.md. The reconciliation state is now confirmed_done, subject to exact-head CI/merge of the closure commit.

## ARV-010 revalidation — 2026-09-20

The historical ARV-010 storage guardrails were followed by merged `OPS-OBSERVABILITY-V1` / PR #76. Current main now has a versioned `/api/ops/observability` snapshot for queue age/depth, ingestion/document failures, storage guard state, backup freshness and recent worker failures, with deterministic warning/critical/unknown semantics plus a non-destructive incident runbook.

The reconciliation overlay marks ARV-010 `confirmed_done` for its repository-side umbrella. This does **not** claim live external notifications, third-party telemetry deployment, production mutation or provider-side monitoring; those remain separately gated scopes.

## ARV-015 revalidation — 2026-09-21

Current main already has a reusable M-006 supplier registry and Decision Core supplier-profile binding, while the RFQ-first `Tender_Operator_Profile_Template.md` defines categories, regions, NMCK/VAT/financial constraints, risk preferences and licenses/SRO. The runtime PP1R parser currently only records profile presence/preview metadata and does not turn those fields into a reusable structured profile.

The bounded non-admitted successor `ARV-015-OPERATOR-PROFILE-PARSER-001` is recorded in `docs/roadmap/ARV-015_REVALIDATION_2026-09-21.md`. It deliberately reuses the existing template and Decision Core; it does not invent a parallel profile subsystem.

## ARV-006 revalidation — 2026-09-21

Merged 223-FZ intake and Decision Core already provide dedicated public search/card intake, source-bound basic facts, document discovery, revision ambiguity guards and fail-closed regime semantics. ARV-006 remains partial: lots/positions and structured changes, clarifications, protocols and status lifecycle are not yet established. One source-traceable successor candidate is recorded as `candidate_not_admitted`; no new 223-FZ implementation or legal rule is authorized by this reconciliation.

## BASE-011 / ARV-004 product-boundary reconciliation — 2026-10-07

BASE-011 is now `confirmed_done` as the Hermes infrastructure foundation. The repository already has the bounded primitives named by the BASE item: client/fallback behavior, runtime context, category profiles, normalization, quality gates, feedback/memory, eval-case generation, supplier-readiness and bid-decision helpers.

The unfinished real-user self-improvement capability is not a BASE prerequisite. It is retained under existing `ARV-004` as the **post-MVP Feedback & Learning Loop**, documented in `docs/product/Feedback_Learning_Loop.md`. ARV-004 is deliberately not admitted to the execution queue at this stage.

The successor loop is constrained to attributable correction → immutable human review → regression case → validated reusable-rule candidate → reviewed promotion. External Hermes runtime is optional, automatic cross-customer learning is prohibited, and canonical HUMAN GO / NO GO / DEFER authority remains unchanged.

## Executor rule

`.agent/execution-queue.yaml` must point back to this master roadmap and may contain only explicitly admitted executable items. The executor may update queue execution status/evidence within its existing authority, but it must not arbitrarily promote a master-roadmap item, resolve an ID collision, change priority/scope, or infer a new ARV mapping by itself.

While `OWNER-CONTINUOUS-ROADMAP-2026-09-18` is active, its deterministic one-at-a-time bounded-materialization rule is itself an explicitly authorized canonical admission mechanism: the watchdog may select the next eligible continuation item in document order and admit only the bounded form permitted by `.agent/owner-directive.yaml`. Outside that mechanism, roadmap promotion still requires Product Owner/Owner or another separately authorized canonical source.
