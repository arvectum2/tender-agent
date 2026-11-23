# Исправление сроков ЕИС: 37 MANAGER_READY — 23 ноября 2026

Задача: `TA-EIS-MANAGER-DEADLINES-20261123` / [#721](https://github.com/arvectum2/tender-agent/issues/721). Выполнено с разрешения владельца после полного аудита 298 строк.

**Итог:** 37 уникальных извещений ЕИС повторно проверены по текущим оригинальным страницам с региональными метками МСК±N и SHA-256; 35 записей с неверными сроками исправлены одной защищённой транзакцией; 2 записи с настоящей полуночью оставлены без изменений. Никакие статусы, заявки, другие сроки или сервисы не изменялись.

Независимое повторное чтение PostgreSQL: 299 строк всего; 35 изменённых сроков совпадают с текущими официальными; остальные 263 из прежнего аудита не изменены; ранее исправленная закупка MAX осталась точной. Подтверждено UTC 2026-11-23T07:09:44.627890+00:00.

**Важно:** исправлены значения текущего рабочего списка, но точное время в исторической редакции извещения на дату первоначального импорта может отличаться. Следует отдельно хранить историю изменений. Текущий развернутый Daily Tender пока использует старую закреплённую версию парсера; внедрение автоматического чтения точного поля ЕИС остаётся самостоятельной задачей.

## В первую очередь — короткие сроки

| Извещение ЕИС | До обновления, МСК | Сейчас, МСК | Исходная зона | Результат |
|---|---|---|---|---|
| [№0853500000326008158](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0853500000326008158) | 24.11.2026 00:00 | 24.11.2026 07:00 | МСК+2 | исправлено |
| [№0162300005326002146](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0162300005326002146) | 24.11.2026 00:00 | 24.11.2026 08:00 | МСК+2 | исправлено |
| [№0137200001226009248](https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0137200001226009248) | 25.11.2026 00:00 | 25.11.2026 08:00 | МСК | исправлено |
| [№0318200064526000132](https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0318200064526000132) | 25.11.2026 00:00 | 25.11.2026 08:00 | МСК | исправлено |
| [№0342200018726000064](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0342200018726000064) | 26.11.2026 00:00 | 25.11.2026 23:00 | МСК+1 | исправлено |
| [№0133200003126000072](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0133200003126000072) | 26.11.2026 00:00 | 26.11.2026 00:00 | МСК | подтверждено, без изменений |
| [№0163200000326005984](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0163200000326005984) | 26.11.2026 00:00 | 26.11.2026 00:00 | МСК | подтверждено, без изменений |
| [№0112200000826005382](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0112200000826005382) | 26.11.2026 00:00 | 26.11.2026 02:00 | МСК+4 | исправлено |
| [№0843500000226006859](https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0843500000226006859) | 26.11.2026 00:00 | 26.11.2026 05:00 | МСК+2 | исправлено |
| [№0853500000326008327](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0853500000326008327) | 26.11.2026 00:00 | 26.11.2026 07:00 | МСК+2 | исправлено |
| [№0137200001226009269](https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0137200001226009269) | 26.11.2026 00:00 | 26.11.2026 08:00 | МСК | исправлено |
| [№0114500000826002658](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0114500000826002658) | 26.11.2026 00:00 | 26.11.2026 09:00 | МСК | исправлено |
| [№0184200000626000970](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0184200000626000970) | 26.11.2026 00:00 | 26.11.2026 09:00 | МСК | исправлено |
| [№0190200000326013981](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0190200000326013981) | 27.11.2026 00:00 | 27.11.2026 06:00 | МСК+2 | исправлено |
| [№0373400007726001146](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0373400007726001146) | 27.11.2026 00:00 | 27.11.2026 07:00 | МСК | исправлено |
| [№0142200001326022921](https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0142200001326022921) | 27.11.2026 00:00 | 27.11.2026 09:00 | МСК+1 | исправлено |
| [№0179200001926000705](https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0179200001926000705) | 27.11.2026 00:00 | 27.11.2026 09:00 | МСК | исправлено |
| [№0373200007026000151](https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0373200007026000151) | 27.11.2026 00:00 | 27.11.2026 09:00 | МСК | исправлено |
| [№0119200000126021522](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0119200000126021522) | 30.11.2026 00:00 | 30.11.2026 04:00 | МСК+4 | исправлено |
| [№0169300000326002843](https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0169300000326002843) | 30.11.2026 00:00 | 30.11.2026 05:00 | МСК+2 | исправлено |
| [№0133200001726003086](https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0133200001726003086) | 30.11.2026 00:00 | 30.11.2026 07:00 | МСК | исправлено |
| [№0154200000726000981](https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0154200000726000981) | 30.11.2026 00:00 | 30.11.2026 07:00 | МСК | исправлено |
| [№0119200000126021114](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0119200000126021114) | 24.11.2026 00:00 | 30.11.2026 07:45 | МСК+4 | исправлено |
| [№0212100001626000047](https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0212100001626000047) | 30.11.2026 00:00 | 30.11.2026 08:00 | МСК+4 | исправлено |
| [№0318300254326000059](https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0318300254326000059) | 30.11.2026 00:00 | 30.11.2026 08:00 | МСК | исправлено |
| [№0811500001126000136](https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0811500001126000136) | 30.11.2026 00:00 | 30.11.2026 08:00 | МСК | исправлено |
| [№0109100004726000017](https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0109100004726000017) | 30.11.2026 00:00 | 30.11.2026 09:00 | МСК | исправлено |
| [№0150200003926001431](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0150200003926001431) | 30.11.2026 00:00 | 30.11.2026 09:00 | МСК | исправлено |
| [№0346500000526000002](https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0346500000526000002) | 30.11.2026 00:00 | 30.11.2026 10:00 | МСК | исправлено |
| [№0244100001726000013](https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0244100001726000013) | 30.11.2026 00:00 | 30.11.2026 14:50 | МСК | исправлено |
| [№0848300069526000449](https://zakupki.gov.ru/epz/order/notice/ok20/view/common-info.html?regNumber=0848300069526000449) | 03.12.2026 00:00 | 03.12.2026 10:00 | МСК | исправлено |
| [№0811500001126000129](https://zakupki.gov.ru/epz/order/notice/ok20/view/common-info.html?regNumber=0811500001126000129) | 04.12.2026 00:00 | 04.12.2026 08:00 | МСК | исправлено |
| [№0811500001126000131](https://zakupki.gov.ru/epz/order/notice/ok20/view/common-info.html?regNumber=0811500001126000131) | 04.12.2026 00:00 | 04.12.2026 08:00 | МСК | исправлено |
| [№0860200000826009491](https://zakupki.gov.ru/epz/order/notice/ok20/view/common-info.html?regNumber=0860200000826009491) | 07.12.2026 00:00 | 07.12.2026 07:00 | МСК+1 | исправлено |
| [№0372100049226000639](https://zakupki.gov.ru/epz/order/notice/ok20/view/common-info.html?regNumber=0372100049226000639) | 07.12.2026 00:00 | 07.12.2026 08:00 | МСК | исправлено |
| [№0811500001126000134](https://zakupki.gov.ru/epz/order/notice/ok20/view/common-info.html?regNumber=0811500001126000134) | 07.12.2026 00:00 | 07.12.2026 08:00 | МСК | исправлено |
| [№0173100003126000056](https://zakupki.gov.ru/epz/order/notice/ok20/view/common-info.html?regNumber=0173100003126000056) | 07.12.2026 00:00 | 07.12.2026 10:00 | МСК | исправлено |

## Доказательства и восстановление

- `plan.json`: SHA-256 `948efab46cad8c99eafc5c6593efdfa4f2bb5fc275dddfa92af89256e47afbbf`; 37 конкретных ID и 35 пар старое→новое, 2 no-op, 37 URL/исходных HTML.
- `db-before.json`: SHA-256 `ae6347e72cbd23f119960e3ab9a168ab718dd8e01b0ae6919b251149eb89520c`; исходные значения 37 записей с полями идентичности, сохранены до COMMIT.
- `commit-intent.json`: SHA-256 `421e79cf29322b834829381ea4565be1a95a5d7c82f8a7de2f77ca1b3c6dbade`; список 35 ID, подлежащих обновлению.
- `commit-verified.json`: SHA-256 `5249866060d16dcc5bc1c5d55bcfa98aa0b769c300b76bb03cb93c8ade6dedd2`; независимая read-only проверка успешного коммита.
- Все файлы и 37 HTML-оригиналов сохранены приватно на Mac mini в каталоге `/Users/master/ArvectumSafe/runtime/ta-source-discovery-20261114/eis-manager-reconcile-20261123` с режимами 0700/0600; оригиналы не выгружены в репозиторий.
- При необходимости отката использовать `db-before.json` и условное восстановление **только** целевых 35 ID, сверив текущее значение/updated_at и источник; не откатывать вслепую при последующих изменениях.

### Проверено

- 25 изолированных профильных pytest PASS, Ruff PASS, Python compile PASS.
- Отдельный пробный прогон 35 условных UPDATE с откатом прошёл; до рабочего изменения каждый из 37 оригиналов ЕИС перепроверен; COMMIT внёс только 35 изменений.
- Независимое повторное чтение всех 299 строк подтвердило отсутствие побочных изменений.


