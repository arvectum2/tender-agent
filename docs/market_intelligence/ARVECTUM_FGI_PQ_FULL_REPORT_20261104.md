# ARVECTUM — полный отчёт Power Quality

Дата исследования: 4 ноября 2026 года. Исторический диапазон: 2023–2026.

Корпус: 123 уникальных лотов; 112 ID процедур;
45 извещений ЕИС 223-ФЗ (46 лотов).

Уровни источников (по лоту): A=43, B=26, C=54, D=0.
Оригинал одного документа не подтверждает все поля сделки.

Материалы:

- [Русский PDF — 406 слайдов](ARVECTUM_FGI_PQ_EXHAUSTIVE_RU_20261104.pdf)
- [English PDF — 406 slides](ARVECTUM_FGI_PQ_EXHAUSTIVE_EN_20261104.pdf)
- [Неизменяемый JSON-корпус](../../data/market_intelligence/power_quality/fgi_full_corpus_20261104.v1.json)
- [Аудит заполненности](ARVECTUM_FGI_PQ_AUDIT_20261104.json)
- [Все сохранённые адреса источников](ARVECTUM_FGI_PQ_SOURCE_LEDGER_20261104.md)

SHA-256 исходного JSON: bd2878b3b024ba90db4b6250b3d7be6263ca1c7211b7035fe8ce1f27c7cbb8d8

## Интерпретация

Спрос включает УКРМ, БСК, STATCOM/SVG, SVC/тиристорную компенсацию, фильтры гармоник, компоненты и EPC.
Это НЕ реестр завершённых контрактов и не полный рынок России. НМЦ, предложение, договор, цена устройства и оплата не складываются в единую выручку.

## Сегменты

| Вид работ | Лотов |
|---|---:|
| supply | 53 |
| epc | 22 |
| design | 17 |
| sounding | 12 |
| components | 8 |
| service | 8 |
| other | 2 |
| mixed_supply | 1 |

## Полнота важных полей

| Поле | Заполнено / всего |
|---|---:|
| buyer_inn | 82 / 123 |
| nmck | 49 / 123 |
| bid | 10 / 123 |
| contract_price | 26 / 123 |
| equipment_only_price | 4 / 123 |
| contract_signed_verified | 20 / 123 |
| signed_supplier_verified | 0 / 123 |
| paid_verified | 0 / 123 |
| voltage_kv | 27 / 123 |
| rated_power | 9 / 123 |
| quantity | 53 / 123 |
| model | 6 / 123 |
| oem_verified | 0 / 123 |
| bidder | 5 / 123 |
| protocol_bidders | 6 / 123 |

## Реестр всех уникальных закупок

Одна строка = один канонический лот. Порядок совпадает с PDF-приложениями.

| № | Канонический ID | Заказчик | Предмет / технология | Вид | НМЦ ₽ | Договор ₽ | Класс |
|---:|---|---|---|---|---:|---:|:---:|
| 1 | [223fz:32313008364:lot1](https://www.dv-tender.ru/details/500280907) | ПАО «Россети» / Забайкальское ПМЭС | Сервисное обслуживание системы охлаждения блоков СТАТКОМ на ПС 220 кВ Могоча | service | 6795960 | — | C |
| 2 | [223fz:32413195287:lot1](https://zakupki.gov.ru/epz/order/notice/notice223/documents.html?purchaseNoticeNumber=32413195287) | ООО «ЕвроЭнергоТранс» | Смешанная закупка ремонта телемеханики 110/10 кВ ОП-4 и капитального ремонта… | epc | 13892027.33 | — | A |
| 3 | [223fz:32413581034:lot2](https://energybase.ru/tender/32413581034) | ПАО «Федеральная сетевая компания – Россети» | Лот 2 — ПС 220 кВ Хани, РД/СМР/ПНР/МТРиО по инвестпроекту СКРМ 128 Мвар Хани… | epc | 1518147770.00 | — | B |
| 4 | [223fz:32413708738:lot1](https://energybase.ru/tender/32413708738) | ПАО «Россети» / МЭС Сибири | Смешанный EPC: реконструкция ПС Туран с ШР/УШР 220 кВ 40 Мвар и БСК 220 кВ… | epc | 826223180.00 | — | B |
| 5 | [223fz:32413764701:lot1](https://zakupki.gov.ru/epz/contractfz223/card/contract-info.html?reestrNumber=58601033125240001550000) | АО «ЮТЭК-Региональные сети» | Аукцион №116/2024: поставка контейнерной УКРМ-А-10,5-150-50-УХЛ1 для… | supply | 3415594.16 | 4077120.00 | A |
| 6 | [223fz:32514476448:lot1](https://zakupki.kontur.ru/32514476448) | ООО «Башкирские распределительные… | 25-000705 Реконструкция ПС Уфимка с установкой БСК 10 кВ, 2×0,9 Мвар | epc | 3176527.55 | 2922405.35 | A |
| 7 | [223fz:32514565977:lot1](https://www.tektorg.ru/223-fz/procedures/13319469) | ОАО «РЖД» | Пусконаладочные работы УКРМП-27,5 кВ на ПС Раздольное (Дальневосточная… | service | 9625921.98 | — | A |
| 8 | [223fz:32514720691:lot1](https://zakupki.gov.ru/epz/order/notice/notice223/common-info.html?regNumber=32514720691) | ООО «Башкирские распределительные… | Поставка двух комплектов УКРМ для ПО НЭС Башкирэнерго, 25-004033; прямой… | supply | 27318000.00 | 14790000.00 | A |
| 9 | [223fz:32514754857:lot1](https://zakupki.gov.ru/epz/order/notice/notice223/common-info.html?regNumber=32514754857) | ООО «Башкирские распределительные… | СМР по реконструкции ПС 110 кВ с монтажом устройств компенсации реактивной… | epc | 7030423.59 | 6732104.09 | A |
| 10 | [223fz:32514944142:lot1](https://energybase.ru/distribution/fsk-ees/tenders/condensers-compensators) | ПАО «Россети» / МЭС Юга | Проектирование замены 3 статических тиристорных компенсаторов на трёх ПС 220… | design | 18668690.00 | — | C |
| 11 | [223fz:32514947144:lot1](https://energybase.ru/distribution/fsk-ees/tenders/condensers-compensators) | ПАО «Федеральная сетевая компания — Россети»,… | Поставка конденсаторов для силовых фильтров для нужд Кузбасского ПМЭС. | components | 3186960 | 3158400.00 | A |
| 12 | [223fz:32515029641:lot1](https://energybase.ru/distribution/fsk-ees/tenders/condensers-compensators) | ПАО «Федеральная сетевая компания — Россети»,… | Поставка конденсаторов для силовых фильтров для нужд филиала ПАО «Россети»… | components | 3621456 | 3490560.00 | A |
| 13 | [223fz:32515044454:lot1](https://energybase.ru/tender/32515044454) | ПАО «Россети Сибирь» | ПИР, корректировка ПД/РД для ПС Тяжинская с заменой БСК-110 на СКРМ 52 Мвар | design | 3031988 | — | C |
| 14 | [223fz:32515208744:lot1](https://poisktenderov.ru/item/223/32515208744/) | ПАО «Федеральная сетевая компания — Россети» | РД, СМР, ПНР и поставка оборудования для реконструкции ПС 220 кВ… | epc | 56688490 | — | B |
| 15 | [223fz:32515218366:lot1](https://synapsenet.ru/zakupki/rts/3611904%231--moskva-pravo-zaklyucheniya-dogovora-na-postavku-sirya-materialov-i) | АО «Россети Научно-технический центр» | Смешанная поставка сырья, материалов и комплектующих для изготовления КВУ,… | supply | 49900000 | 49900000.00 | A |
| 16 | [223fz:32515225588:lot1](https://energybase.ru/distribution/fsk-ees/tenders/condensers-compensators) | ПАО «Федеральная сетевая компания — Россети» | Разработка проектной документации по реконструкции системы компенсации… | design | 27175270 | 20442391.10 | A |
| 17 | [223fz:32515582393:lot1](https://synapsenet.ru/zakupki/b2b/4283612--bashkortostan-resp-postavka-ustanovki-kondensatornoj-ukrm-dlya-po-nes) | ООО «Башкирэнерго» | Поставка конденсаторной установки УКРМ для ПО НЭС, заявка 26-003065. | supply | 5880000 | 4850000.00 | A |
| 18 | [223fz:32515584863:lot1](https://poisktenderov.ru/item/223/32515584863/) | ПАО «Россети» / МЭС Востока | Корректировка проектной документации общего титула с установкой двух систем… | design | 11583990.00 | — | C |
| 19 | [223fz:32615614821:lot1](https://zakupki.kontur.ru/32615614821) | ООО «Башкирские распределительные… | Реконструкция подстанции в части установки устройств компенсации реактивной… | epc | 1432983.66 | 1833358.30 | A |
| 20 | [223fz:32615637628:lot1](https://zakupki.gov.ru/epz/order/notice/notice223/contract/printForm/viewXml.html?contractRegistrationNumber=52460069527260002170001) | ПАО «Россети Сибирь» | Поставка 2 конденсаторов КЭПФ-11,55-500-2УХЛ1: 11,55 кВ, по 500 квар.… | supply | 531888.28 | 484998.80 | A |
| 21 | [223fz:32615684088:lot1](https://zakupki.gov.ru/epz/order/notice/notice223/contract-info.html?purchaseNoticeNumber=32615684088) | ПАО «Россети Центр» | Строительство ВЛ 10 кВ, установка реклоузера и двух разъединителей 10 кВ,… | epc | 37828258.18 | 37818258.18 | A |
| 22 | [223fz:32615760238:lot1](https://poisktenderov.ru/item/223/32615760238/) | ПАО «Россети» / МЭС Востока | Дополнительная/повторная закупка ПИР по проекту двух СКРМ на ПС Хани и Лопча | design | 11635890.00 | — | C |
| 23 | [223fz:32615794236:lot1](https://zakupki.kontur.ru/32615794236) | ПАО «Россети» / МЭС Сибири | Проектирование установки БСК 110 кВ ≥5 Мвар на ПС Чадан | design | 3584659.00 | 3579778.90 | B |
| 24 | [223fz:32615852898:lot1](https://vsem-podryad.ru/purchase/047e95d3-73dd-4628-a32d-82f3159fe5dc/) | ПАО «Россети Сибирь» / Кузбассэнерго-РЭС | ПИР по реконструкции ВЛ 10 кВ с ПАРН/ВДТ и устройством компенсации… | design | 2950502.46 | 2787700.00 | A |
| 25 | [223fz:32615937898:lot1](https://int.zakupki.gov.ru/eis-integration/services/getDocsIP) | АО «Россети Научно-Технический Центр» | Проектные и изыскательские работы по реконструкции ПС 110/35/10 кВ Тяжинская… | design | 3050000.00 | 3050000.00 | A |
| 26 | [223fz:32615966040:lot1](https://synapsenet.ru/zakupki/fz223/32615966040%231--moskva-vipolnenie-smr-pnr-materiali-i-oborudovanie-po-titulu) | ПАО «Россети Московский регион» | Комплекс ПИР, СМР, ПНР, оборудование 10кВ КРУ и компенсация реактивной… | epc | 5273764.00 | 5273763.77 | A |
| 27 | [223fz:32615969197:lot1](https://zakupki.kontur.ru/32615969197) | ООО «Башкирские распределительные… | ПИР на установку УКРМ 10 кВ | design | 518960 | — | A |
| 28 | [223fz:32616065155:lot7](https://www.b2b-center.ru/market/postavka-elektrotekhnicheskogo-oborudovaniia-vykliuchateli/tender-4469608/) | ООО «ТН-Энергосбыт» | Лот №7. Установки конденсаторные (1 комплект) в 11-позиционной закупке… | supply | 3172000.00 | — | A |
| 29 | [223fz:32616103025:lot1](https://zakupki.gov.ru/epz/order/notice/notice223/documents.html?purchaseNoticeNumber=32616103025) | ООО «Башкирские распределительные… | Повторный конкурс на выполнение ПИР по УКРМ 10 кВ ПС 35кВ Пионерская; тот же… | design | 518960.00 | — | B |
| 30 | [223fz:32616120582:lot1](https://vsem-podryad.ru/purchase/f088b62a-cca2-493e-b887-1653bae98839/?backUrl=%2Fnowinnerpurchases%2F%3FisSmbRequired%3D1%26purchaseFzs%3DFz223%2CFz615) | ПАО «Россети Северо-Запад» | Полный комплекс работ под ключ: ЛЭП 6 кВ 0,175 км, монтаж конденсаторной… | epc | 21120361.66 | 17000000.00 | A |
| 31 | [223fz:32616181358:lot1](https://zakupki.gov.ru/epz/contractfz223/card/contract-info.html?reestrNumber=57724646338260000460000) | АО «Завод РЭТО» | Подписанный реестровый договор 223-ФЗ №57724646338260000460000, 19.08.2026,… | supply | 3078500.00 | 3050000.00 | A |
| 32 | [223fz:32616266007:lot1](https://zakupki.gov.ru/epz/order/notice/notice223/documents.html?purchaseNoticeNumber=32616266007&noticeGuid=02d450e6-9e48-40f6-82a3-bbb1b3bfb3e0) | ПАО «Россети» — МЭС Центра | Поставка пяти конденсаторов БСК в аварийный запас для ПС 500 кВ «Калужская».… | components | 856440.00 | 662460.00 | A |
| 33 | [223fz:32616280467:lot1](https://zakupki.gov.ru/epz/order/notice/notice223/documents.html?purchaseNoticeNumber=32616280467) | ПАО «Россети Волга» | ПИР по системе динамической компенсации реактивной мощности на ВЛ-10 кВ,… | design | 3683790.00 | 3680106.21 | A |
| 34 | [223fz:32616296475:lot1](https://zakupki.tochka.com/search/22844514-1/) | ООО «Водоканал», г. Мелеуз | Поставка автоматического устройства компенсации реактивной мощности с… | mixed_supply | 3904773.73 | 3865725.99 | A |
| 35 | [223fz:32616339168:lot1](https://energybase.ru/tender/01a05c2b-28c2-7170-bc05-f33a221d5042) | ПАО «Россети» / МЭС Юга | 24 отдельных конденсатора батарей статических конденсаторов для… | components | 6807600.00 | 4350000.00 | A |
| 36 | [223fz:32616354211:lot1](https://energybase.ru/tender/01a08049-5098-7347-9eff-5553da0043ea) | АО «Энергосервисная компания Сибири» | Изыскания и разработка ПД реконструкции ПС Тяжинская с заменой БСК-110 на… | design | 7519646.09 | 7406851.40 | A |
| 37 | [223fz:32616355390:lot1](https://zakupki.gov.ru/223/filestore/public/1.0/download/fz223/file.html?uid=C3F84B482EE34CF294EB7B95AEC46D97) | АО «Россети Научно-технический центр» | Поставка сырья, материалов и комплектующих по заявкам для производства… | other | 399120963.00 | — | A |
| 38 | [223fz:32616400421:lot1](https://energybase.ru/tender/01a0d2b3-4a2d-71cc-a3c9-231192b45751) | ПАО «Россети Сибирь», Кузбассэнерго-РЭС | Конкурс №26-1149: поставка батарей статических конденсаторов,… | supply | 452016000.01 | — | A |
| 39 | [223fz:32616412267:lot1](https://zakupki.gov.ru/epz/order/notice/notice223/documents.html?purchaseNoticeNumber=32616412267) | МУП Ангарского городского округа «Ангарский… | Испытания оборудования, проверка и наладка защит восьми ячеек РУ-6кВ… | service | 4295282.00 | 2639026.64 | A |
| 40 | [223fz:32616430382:lot1](https://zakupki.gov.ru/epz/order/notice/notice223/common-info.html?regNumber=32616430382) | ПАО «Федеральная сетевая компания — Россети» | Реконструкция ПС 220 кВ «Полупроводники»: замена компенсирующих устройств в… | epc | 72183607.13 | — | A |
| 41 | [223fz:32616433248:lot1](https://zakupki.gov.ru/epz/order/notice/notice223/documents.html?purchaseNoticeNumber=32616433248) | ПАО «Россети Северо-Запад» | Одна ступенчатая УКРМ не менее 3,5 Мвар на шинах 35 кВ, основная ступень… | epc | 56330673.93 | — | A |
| 42 | [223fz:32616435269:lot1](https://kontendus.ru/tender/32616435269) | ПАО «Россети Сибирь», филиал… | Поставка батарей статических конденсаторов для Кузбассэнерго-РЭС. Открытые… | supply | 452016000.01 | — | A |
| 43 | [223fz:32616474682:lot1](https://www.b2b-center.ru/market/postavka-kondensatorov-kep-dlia-ooo-bashkirenergo-ooo-bsk-27-000090/tender-4642507/?action=positions) | ООО «Башкирская сетевая компания» | Конденсаторы КЭП, код ОКПД2 27.90.51.000; 11 шт. для ООО БСК. | components | 981354.33 | — | B |
| 44 | [223fz:32616474682:lot2](https://www.b2b-center.ru/market/postavka-kondensatorov-kep-dlia-ooo-bashkirenergo-ooo-bsk-27-000090/tender-4642507/?action=positions) | ООО «Башкирские распределительные… | Конденсаторы КЭП, код ОКПД2 27.90.51.000; 16 шт. для ООО Башкирэнерго. | components | 1471296.08 | — | B |
| 45 | [223fz:32616497692:lot1](https://zakupki.gov.ru/epz/order/notice/notice223/documents.html?purchaseNoticeNumber=32616497692) | ПАО «Россети Северо-Запад» | Под ключ: монтаж одной УКРМ 10 кВ 3 Мвар (УКРЛ56 10,5-3150-900 У1 или… | epc | 79101498.40 | — | A |
| 46 | [223fz:32616506708:lot1](https://zakupki.kontur.ru/32616506708) | АО «Россети Научно-Технический Центр» | Корректировка ПСД этапа 3 реконструкции ПС 220 кВ Ванино с установкой СКРМ… | design | 13523603.17 | — | C |
| 47 | [223fz:chges24621PR:lot1](https://synapsenet.ru/zakupki/lotonline/chges24621pr--stavropolskij-kraj-postavka-4-chetireh-shtuk-avtomaticheskih) | АО «ЧиркейГЭСстрой» | Поставка автоматических регулируемых конденсаторных установок УКРМ для КТП | supply | — | — | C |
| 48 | [223fz:judicial-contract-03-34-24:lot1](https://sudact.ru/arbitral/doc/adOxeAqN4doN/) | АО «Тюменьэнерго Инжиниринг» | Поставка одной УКРМ-10,5-13000-13х1000р У3 с БКМУ (БМЗ), договор 29.10.2024,… | supply | — | — | B |
| 49 | [aggregator:2418411721:lot1](https://www.komtender.ru/category/tendery-ugmk?page=4&pg=3&scrollto=table-constructor) | Заказчик не установлен | Конденсаторная установка регулируемая «1.8-УКРЛ 6 кВ»; модель и количество… | supply | — | — | C |
| 50 | [commercial:106044-ТТ:lot1](https://zakupki.kontur.ru/IS55137357) | АО «УК «Кузбассразрезуголь» | СТАТКОМ для Калтанского угольного разреза (2 шт.) и Талдинского (1 шт.) | supply | — | — | C |
| 51 | [commercial:111098-ТТ:lot1](https://zakupki.kontur.ru/IS56504786) | ПАО «Гайский горно-обогатительный комбинат» | Поставка 2 шт. УКРМ-6,3-600 (600 квар, 6 кВ), первая обнаруженная процедура… | supply | — | — | C |
| 52 | [commercial:1148520:lot1](https://zakupki.tochka.com/search/1084879614-3/) | ООО «Инженерно-Строительная Компания» | Статический компенсатор реактивной мощности для строительства ЦОД, 1… | supply | — | — | C |
| 53 | [commercial:1190793:lot1](https://zakupki.kontur.ru/IS59537488) | ООО «Завод Технофлекс», филиал г. Учалы | Запрос предложений на поставку шкафов ВРУ, КСО, КТПВ, УКРМ (смешанный лот) | supply | — | — | C |
| 54 | [commercial:119199-ТТ:lot1](https://zakupki.kontur.ru/IS58063586) | ПАО «Гайский горно-обогатительный комбинат» | Поставка двух УКРМ-6,3-600 (6 кВ, 600 квар каждая) с шефмонтажом и… | supply | — | — | C |
| 55 | [commercial:1216754:lot1](https://zakupki.kontur.ru/category-region/raznoe-oborudovanie-komplektuyushhie-cyre-i-materialy/uchaly) | Филиал ООО «Завод Технофлекс», Учалы | Запрос цен на приобретение УКРМ | supply | — | — | C |
| 56 | [commercial:1221629:lot1](https://zakupki.kontur.ru/IS67789174) | ООО «Исо» (филиал в Братске) | Смешанный ТМЦ-лот с двумя фильтрами гармоник АФГ-0,4-150-1-Н У3 среди… | supply | — | — | C |
| 57 | [commercial:1234013:lot1](https://zakupki.kontur.ru/IS71078051) | ООО «Завод Технофлекс», филиал г. Учалы | Запрос предложений на поставку шкафов ВРУ, КСО, КТПВ, УКРМФ (смешанный лот) | supply | — | — | C |
| 58 | [commercial:130233-ТТ:lot1](https://zakupki.kontur.ru/category-region/raznoe-oborudovanie-komplektuyushhie-cyre-i-materialy/uchaly) | АО «Учалинский ГОК» | Установка УКРМ-0,4-200 по ТЗ | supply | — | — | C |
| 59 | [commercial:135171-ТТ:lot1](https://zakupki.kontur.ru/IS69557584) | ПАО «Гайский горно-обогатительный комбинат» | Поставка 2 УКРМ-6,3-600 (6 кВ, 600 квар) с шефмонтажными и шефналадочными… | supply | — | — | C |
| 60 | [commercial:2103585-2:lot1](https://sibur.ru/ru/procurement/buy/archive/?procedure=2103585%2F2) | ООО «ЗапСибНефтехим» | Установка компенсации реактивной мощности 10 кВ для ДГП-2; повторная… | other | — | — | C |
| 61 | [commercial:2128160-1:lot1](https://sibur.ru/ru/procurement/buy/archive/?procedure=2128160%2F1) | ООО «НПП «Нефтехимия» | ПИР модернизации РП-115/116, проектирование 3 регулируемых БСК 6 кВ | design | — | — | C |
| 62 | [commercial:231994-2:lot1](https://synapsenet.ru/zakupki/fosagro/231994-2--murmanskaya-obl-2319942-dopolnenie-rd-ps352-sistema-dinamicheskoj) | АО «Апатит» (Кировский филиал) | Дополнительный тендер на РД системы динамической компенсации, ГС-2… | design | — | — | C |
| 63 | [commercial:231994:lot1](https://zakupki.kontur.ru/IS58580517) | АО «Апатит» (Кировский филиал) | Разработка рабочей документации на динамическую компенсацию реактивной… | design | — | — | B |
| 64 | [commercial:281-705:lot1](https://bidzaar.com/app/process/light/019b4fe0-38ca-773a-91b0-0ff33daedb7d) | Русагро — сахарные заводы | Проектирование мест установки фильтров гармоник и электрических схем семи… | design | — | — | A |
| 65 | [commercial:306-644:lot35](https://bidzaar.com/app/process/light/019ce668-617b-7b1a-861e-113ed78182af) | СИБСТЕКЛО | Монтаж, подключение и ПНР установок УКРМ 6 кВ в СК-3, лот 35; опубликованы… | epc | — | — | A |
| 66 | [commercial:351-062:lot1](https://bidzaar.com/app/process/light/019f415c-8a7a-7c91-bb3f-68da7b9413ea) | АО «ГК «Электрощит»-ТМ Самара» | Анализ цен двух конденсаторных установок УКРМ 6 кВ, заявка 300240128;… | supply | — | — | B |
| 67 | [commercial:358-830:lot1](https://bidzaar.com/app/process/light/019fb323-f23b-7872-845e-ba2cb6b43355) | Не раскрыт на публичной карточке Bidzaar | Поставка активных фильтров гармоник (3 штуки), возможны аналоги по ТЗ | supply | — | — | B |
| 68 | [commercial:364-959:lot1](https://zakupki.kontur.ru/customers/5047175485) | ООО УК «Мега» | Техническое обслуживание дизель-генераторов, пожарных насосов и станций УКРМ | service | — | — | C |
| 69 | [commercial:4158439:lot1](https://www.b2b-center.ru/market/modernizatsiia-ustanovki-kompensatsii-reaktivnoi-moshchnosti-ukrm/tender-4158439/) | ООО «ЭЛЬБРУС ДРИЛЛИНГ» | Модернизация установки компенсации реактивной мощности (УКРМ) | service | — | — | A |
| 70 | [commercial:4256170:lot1](https://zakupki.kontur.ru/4256170_4) | ООО «Прогазстрой» | Поставка двух конденсаторных установок УКРМ-10кВ по отдельным позициям: 1600… | supply | — | — | C |
| 71 | [commercial:4263966:lot1](https://www.b2b-center.ru/app/market-next/2744415-ustanovka-reguliruemaia-dlia-kompensatsii-reaktivnoi/tender-4263966/) | ПАО «Уралкалий» | Регулируемая установка компенсации реактивной мощности 200 квар, 10 кВ, 1… | supply | — | — | A |
| 72 | [commercial:4302914:lot1](https://synapsenet.ru/zakupki/b2b/4302914--belgorodskaya-obl-tehnicheskoe-obsluzhivanie-oborudovaniya) | АО «Лебединский ГОК» | ТО конденсаторной установки СТАТКОМ RU-DRIVE SVG 6,3/5-3 МВАр | service | — | — | C |
| 73 | [commercial:4304120:lot1](https://zakupki.kontur.ru/4304120_458) | ООО «НГК Ресурс» | Поставка двух УКРМ 350 кВАр | supply | — | — | C |
| 74 | [commercial:4526968:lot1](https://zakupki.kontur.ru/4526968_4) | ООО «Мелькомбинат» | Изготовление и поставка четырех установок УКРМ по опросному листу заказчика. | supply | — | — | C |
| 75 | [commercial:4535313:lot1](https://rostender.info/region/buryatiya-respublika/93906192-tender-zakupka-kondensatornoj-ustanovki-srednego-napryajeniya-ukrm-6kv-630-kvar) | Заказчик не установлен | Закупка конденсаторной установки среднего напряжения УКРМ 6 кВ 630 квар. | supply | — | — | C |
| 76 | [commercial:4559984:ukrm-6p3-component](https://synapsenet.ru/zakupki/b2b/4559984--hantimansijskij-ao-zapros-kommercheskih-predlozhenij-na-postavku-mtr) | ООО «Аргос-Строй» / филиал «Прометей» | Запрос КП на МТР для ПС 35/6кВ Тевлинско-Русскинского: 1… | sounding | — | — | A |
| 77 | [commercial:4561228:lot1](https://zakupki.kontur.ru/4561228_4) | АО «Михайловский ГОК им. А. В. Варичева» | Две конденсаторные установки 10 кВ АУКРМ (УК1, УК2). | supply | — | — | C |
| 78 | [commercial:4561243:lot1](https://synapsenet.ru/zakupki/b2b/4561243--kurskaya-obl-zakupka-kondensatornih-ustanovok-10-kv-aukrm-uk3-uk4-dlya) | АО «Михайловский ГОК им. А. В. Варичева» | Две конденсаторные установки 10 кВ АУКРМ (УК3, УК4). | supply | — | — | C |
| 79 | [commercial:4565274:lot1](https://synapsenet.ru/zakupki/b2b/4565274--kurskaya-obl-zakupka-kondensatornoj-ustanovki-10-kv-aukrm-uk1-uk2-dlya) | АО «Михайловский ГОК им. А. В. Варичева» | Закупка одной позиции (2 шт.) конденсаторных установок АУКРМ 10 кВ УК1/УК2,… | supply | — | — | C |
| 80 | [commercial:4617521:lot1](https://www.b2b-center.ru/app/market-next/vybor-ispolnitelia-na-postavku-montazh-i-pnr-ustanovok-kompensatsii/tender-4617521/) | АО «Тандер» | Поставка, монтаж и ПНР установок компенсации реактивной мощности для ТДХ… | epc | — | — | A |
| 81 | [commercial:4643332:lot1](https://www.b2b-center.ru/market/808-kondensator-kep3-10-5-150-3u2/tender-4643332/) | АО «Ванинотрансуголь» (АО «ВТУ») | Закупка одного конденсатора КЭП3-10,5-150-3У2 номинальным напряжением 10,5… | supply | — | — | B |
| 82 | [commercial:4657777:lot1](https://www.b2b-center.ru/market/postavka-blokov-kondensatornykh-dlia-nuzhd-po-btses-po-kes-ooo/tender-4657777/) | ООО «Башкирэнерго» | Шесть конденсаторных блоков для ПО БцЭС и ПО КЭС; напряжение не раскрыто в… | components | — | — | A |
| 83 | [commercial:5534/1866-УДСН:lot1](https://uds-group.ru/tenders/oil-production/?sphrase_id=10398) | UDSgroup (exact legal buyer unverified) | BСК-10-5 УХЛ1; delivery Izhevsk | supply | — | — | B |
| 84 | [commercial:5631/018-Ял:lot1](https://uds-group.ru/tenders/oil-production/?sphrase_id=10398) | UDSgroup (exact legal buyer unverified) | BСК10-0.5 and БСК6-0.5; delivery Ялыкское месторождение | supply | — | — | B |
| 85 | [commercial:5747901:lot1](https://synapsenet.ru/zakupki/zakupkimosru/5747901--neneckij-aokr-modernizaciya-ustanovki-kompensacii-reaktivnoj) | ООО «ЭЛЬБРУС ДРИЛЛИНГ» | Модернизация существующей УКРМ буровой установки согласно ТЗ_Т45, один… | service | — | — | C |
| 86 | [commercial:77795100:lot1](https://rostender.info/category/tendery-gk-elektroshchit) | АО «ГК «Электрощит» — ТМ Самара» | Поставка УКРМ | supply | — | — | C |
| 87 | [commercial:77907981:lot1](https://rostender.info/category/tendery-gk-elektroshchit) | АО «ГК «Электрощит» — ТМ Самара» | УКРМ с фильтрами гармоник | supply | — | — | C |
| 88 | [commercial:834269:lot1](https://www.tender.pro/api/tender/834269/view_public) | — | ЭТП Tender.Pro №834269, создан 06.12.2023: лот №1 на 4 комплекта устройств… | supply | — | — | B |
| 89 | [commercial:86829457:lot1](https://rostender.info/category/tendery-npp-izmeritel?page=1) | Не раскрыт на доступной публичной карточке | Поставка устройства компенсации реактивной мощности УКРМ-10,5-450 | supply | — | — | C |
| 90 | [commercial:895449:lot1](https://zakupki.kontur.ru/IS44114609) | АО «Русская Медная Компания» | Поставка, монтаж и ПНР трёх трансформаторных подстанций 10/0,4 кВ (ТП2, ТП3,… | epc | — | — | C |
| 91 | [commercial:945712:lot1](https://zakupki.kontur.ru/IS77008483) | АО «НК «Конданефть» | Поставка девяти низковольтных УКРМ 0,4 кВ: по позициям 2+4+2+1 шт, лот… | supply | — | — | C |
| 92 | [commercial:COM07102500074:lot1](https://zakupki.kontur.ru/IS54665725) | ООО «ЛУКОЙЛ-Западная Сибирь» | Поставка установок УКРМ для территориально-производственных предприятий | supply | — | — | C |
| 93 | [commercial:COM16012600053:lot1](https://zakupki.kontur.ru/IS56822445) | ООО «ЛУКОЙЛ-Западная Сибирь» | Поставка УКРМ для территориально-производственных предприятий | supply | — | — | C |
| 94 | [commercial:COM20082600016:lot1](https://synapsenet.ru/zakupki/roseltorg/com20082600016%231--hantimansijskij-ao-postavka-ustanovki-kompensacii) | ООО «ЛУКОЙЛ-Западная Сибирь» | Запрос ценовой информации на 1 комплект установки компенсации реактивной… | sounding | — | — | C |
| 95 | [commercial:RAD260049805:lot1](https://zakupki.kontur.ru/IS79649770) | АО «Дальневосточная распределительная сетевая… | СМР и рабочая документация: реконструкция ПС Пограничная, монтаж линейной… | epc | — | — | C |
| 96 | [commercial:UKK-0SCS-3-102:lot1](https://rutend.ru/customers/1095243?page=7) | ООО «ЕвроХим — Усольский калийный комбинат» | СМР и электроснабжение фильтрокомпенсирующего устройства ствола №3, включая… | epc | — | — | C |
| 97 | [commercial:unverified-rosneft-2025-02-28-ukrm6kv-blockbox:lot1](https://energybase.ru/integrated/rosneft/tenders/condensers-compensators) | ПАО «НК «Роснефть» (агрегаторный организатор) | Поставка установки компенсации реактивной мощности в блок-боксе «УКРМ 6 кВ»;… | supply | — | — | C |
| 98 | [commercial:unverified-suhodol-2025-07-17:lot1](https://b2b.house/purchase/r805b9b2c-cd4d-4254-bba1-5deb6fd5d9bf_4b62e826/) | ООО «Морской порт «Суходол» | Проектирование, изготовление, поставка, монтаж и ПНР СТАТКОМ с активной… | epc | — | — | C |
| 99 | [commercial:АП125337:lot1](https://zakupki.kontur.ru/AP125337) | ООО «Газпром бурение» | Поставка двух УКРМ-6,3 (10,5)-3150-450 3х450ф+4х450р. | supply | — | — | C |
| 100 | [commercial:ГП630876:lot1](https://synapsenet.ru/zakupki/gazprombank/%D0%B3%D0%BF630876%231344734--leningradskaya-obl-postavka-oborudovaniya-s) | ООО «НОВАТЭК-УСТЬ-ЛУГА» | Поставка оборудования с работами по модернизации существующей УКРМ 10 кВ; в… | epc | — | — | C |
| 101 | [commercial:РН41205245:lot1](https://zakupki.kontur.ru/IS48834468) | ООО «РН-Ванкор» (организатор закупки… | РНВ-24-МТР-2600065317 — поставка установок компенсации реактивной мощности с… | supply | — | — | C |
| 102 | [commercial:РН50303773:lot1](https://zakupki.kontur.ru/IS50374166) | ПАО «НК «Роснефть» (корпоративный организатор) | Поставка НКУ и УКРМ, ТЭК-Торг РН50303773 | sounding | — | — | C |
| 103 | [commercial:РН51202455:lot1](https://zakupki.kontur.ru/IS56433497) | ООО «РН-Бурение» | Техническое сопровождение с использованием установки компенсации реактивной… | service | — | — | C |
| 104 | [commercial:РН60802401:lot1](https://zakupki.kontur.ru/category-region/transformatory-transformatornye-podstancii-i-reaktory/udmurtia) | ПАО «Удмуртнефть» им. В. И. Кудинова | Опрос рынка на изготовление и поставку УКРМ-6-1-А900-450+2х225-Л1Н2Х6 | supply | — | — | C |
| 105 | [commercial:РН60804549:lot1](https://zakupki.kontur.ru/category-region/raznoe-oborudovanie-komplektuyushhie-cyre-i-materialy/gubkinskij) | ООО «Севкомнефтегаз» | Поставка УКРМ для нужд ООО СКН | supply | — | — | C |
| 106 | [commercial:РН61001644:lot1](https://zakupki.kontur.ru/category-region/raznoe-oborudovanie-komplektuyushhie-cyre-i-materialy/gubkinskij) | ООО «Севкомнефтегаз» | Поставка УКРМ | supply | — | — | C |
| 107 | [commercial:РН61003961:lot1](https://www.tektorg.ru/rosneft/procedures?name=%D0%A0%D0%9D61003961) | АО «АНПЗ ВНК» | Установки конденсаторные, лот 2600124554. Оригинальная таблица критериев… | supply | — | — | A |
| 108 | [commercial:РН61004155:lot1](https://zakupki.kontur.ru/IS82581020) | ООО «Башнефть-Добыча» | Коммерческий запрос оферт на поставку установок компенсации реактивной… | supply | — | — | A |
| 109 | [commercial:РН61005187:lot1](https://zakupki.kontur.ru/category-region/raznoe-oborudovanie-komplektuyushhie-cyre-i-materialy/uralskij-federalnyj-okrug) | ООО «Харампурнефтегаз» | Поставка ДФКУ, УКРМ | supply | — | — | A |
| 110 | [index:energybase:rosneft-pq-20231109-kharampur](https://energybase.ru/integrated/rosneft/tenders/condensers-compensators) | ПАО «НК «Роснефть» (корпоративный организатор) | Опрос рынка на поставку УКРМ для ООО Харампурнефтегаз | sounding | — | — | B |
| 111 | [index:energybase:rosneft-pq-20231201-kharampur](https://energybase.ru/integrated/rosneft/tenders/condensers-compensators) | ПАО «НК «Роснефть» (корпоративный организатор) | Повторный опрос рынка на поставку УКРМ для ООО Харампурнефтегаз | sounding | — | — | B |
| 112 | [index:energybase:rosneft-pq-20240124-rospan](https://energybase.ru/integrated/rosneft/tenders/condensers-compensators) | ПАО «НК «Роснефть» (корпоративный организатор) | Опрос рынка на поставку УКРМ для АО РОСПАН ИНТЕРНЕШНЛ | sounding | — | — | B |
| 113 | [index:energybase:rosneft-pq-20240320-bashneft-polyus](https://energybase.ru/integrated/rosneft/tenders/condensers-compensators) | ПАО «НК «Роснефть» (корпоративный организатор) | Опрос рынка на поставку конденсаторной установки для Башнефть-Полюс | sounding | — | — | B |
| 114 | [index:energybase:rosneft-pq-20240411-kharampur](https://energybase.ru/integrated/rosneft/tenders/condensers-compensators) | ПАО «НК «Роснефть» (корпоративный организатор) | Опрос рынка на поставку УКРМ для ООО Харампурнефтегаз | sounding | — | — | B |
| 115 | [index:energybase:rosneft-pq-20240423-kharampur](https://energybase.ru/integrated/rosneft/tenders/condensers-compensators) | ПАО «НК «Роснефть» (корпоративный организатор) | Опрос рынка на поставку УКРМ для ООО Харампурнефтегаз | sounding | — | — | B |
| 116 | [index:energybase:rosneft-pq-20240427-nizhnevartovsk](https://energybase.ru/integrated/rosneft/tenders/condensers-compensators) | ПАО «НК «Роснефть» (корпоративный организатор) | Запрос цен на поставку УКРМ для Нижневартовского филиала | sounding | — | — | B |
| 117 | [index:energybase:rosneft-pq-20240517-kharampur-nku](https://energybase.ru/integrated/rosneft/tenders/condensers-compensators) | ПАО «НК «Роснефть» (корпоративный организатор) | Опрос рынка на поставку НКУ и УКРМ для Харампурнефтегаз | sounding | — | — | B |
| 118 | [index:energybase:rosneft-pq-20250410-rospan-ktp-ukrm](https://energybase.ru/integrated/rosneft/tenders/condensers-compensators) | ПАО «НК «Роснефть» (корпоративный организатор) | Опрос рынка на поставку КТП и УКРМ для РОСПАН ИНТЕРНЕШНЛ | sounding | — | — | B |
| 119 | [index:rostender:88416730](https://rostender.info/category/tendery-na-vozdushnye-filtry?page=327&scrollto=table-constructor) | Не раскрыт в индексированной выдаче | Поставка трехфазного фильтр-реактора для фильтра гармоник тока в сети 10 кВ | components | — | — | B |
| 120 | [index:vsempodryad:9d4a58cf-6c10-4485-8537-53e550c24269](https://vsem-podryad.ru/purchase/9d4a58cf-6c10-4485-8537-53e550c24269/) | ПАО «Федеральная сетевая компания – Россети» | Лот 1 — ПС 220 кВ Лопча, РД/СМР/ПНР/МТРиО; инвестиционный проект СКРМ 154… | epc | 1571458880.00 | 1571458880.00 | C |
| 121 | [index:vsempodryad:ea5a381b-31b1-4c37-962f-9fddf1761b74](https://vsem-podryad.ru/purchase/ea5a381b-31b1-4c37-962f-9fddf1761b74/) | ПАО «Россети Юг», филиал «Волгоградэнерго» | Поставка батарей статических конденсаторов БСК, 7 шт. для «Волгоградэнерго» | supply | 10880835.00 | 10880835.00 | C |
| 122 | [index:vsempodryad:tplus-samara-gres-reactive-20240427](https://vsem-podryad.ru/nowinnerpurchases/?hasParticipants=1&page=193&purchaseFzs=Fz44%2CFz223%2CFz615%2CCommercial) | ПАО «Т Плюс» | Поставка устройств компенсации реактивной мощности для нужд Самарской ГРЭС | supply | — | — | B |
| 123 | [platform:1351/ОАЭ-ЦДКС/26:lot1](https://synapsenet.ru/zakupki/rts/1351%D0%BE%D0%B0%D1%8D-%D1%86%D0%B4%D0%BA%D1%8126%231--irkutskaya-obl-otkritij) | ОАО «РЖД» | Вторые питания 5 единиц устройств компенсации реактивной мощности в… | epc | 36289595.00 | — | C |

## Границы использования

- Нет права выводить подписавшего поставщика из одного протокольного победителя.
- Без выделенной номенклатуры цена комплексного EPC не равна цене УКРМ/STATCOM.
- Отсутствие строки оплаты или OEM — не доказательство отсутствия факта.
- Существующие URL могут стать недоступны после выгрузки; исторический SHA не подтверждает их доступность на текущую дату.
- Каждый из 123 лотов представлен на трёх отдельных страницах PDF; шесть случаев с исходными списками участников дополнены отдельными страницами протоколов.
