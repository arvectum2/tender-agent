# Полный аудит сроков 298 записей ЕИС — 23 ноября 2026

Снимок реальной рабочей БД, 298 строк, 196 уникальных извещений; снято в режиме REPEATABLE READ READ ONLY. SHA снимка: 47cae7aea67ded3c39af1cc0fd2808d9abf2af441fa3233605780d2ab28a1d27. Повторно проверены все 196 исходных HTML ЕИС, их SHA-256, номера извещений и квитанции сохранения.

**Итоги сравнения с текущей официальной редакцией:** **288** — та же московская дата, но отличается время; **7** — отличается московская календарная дата; **3** — точное совпадение; **0** — не проверено. По сравнению с БД 293 официальных срока позже, 2 раньше, 3 совпадают.

Состояние MANAGER_READY: 45 записей, из них 37 с будущим сроком по ЕИС. Всего записей с будущим официальным сроком: 225.

**Ограничение:** сверка относится к текущему официальному извещению, не к каждой его исторической редакции. Часть сроков могла измениться после первоначального импорта. Не выполнено ни одного UPDATE БД, автоматической коррекции статусов или подачи заявок.

## Особо опасные расхождения — ЕИС раньше БД

| Извещение | Статус | В БД, МСК | В ЕИС, МСК | Сдвиг |
|---|---|---|---|---|
| [№0342200018726000064](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0342200018726000064) | MANAGER_READY | 2026-11-26 00:00 | 2026-11-25 23:00 | -1 ч |
| [№0342200018726000064](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0342200018726000064) | DUPLICATE | 2026-11-26 00:00 | 2026-11-25 23:00 | -1 ч |

## Отличается календарная дата по Москве

| Извещение | Статус | БД | ЕИС | Пояс в ЕИС |
|---|---|---|---|---|
| [№0119200000126021114](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0119200000126021114) | MANAGER_READY | 2026-11-24 00:00 | 2026-11-30 07:45 | МСК+4 |
| [№0169300000126001582](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0169300000126001582) | SCREENED_OUT | 2026-11-24 00:00 | 2026-11-25 07:00 | МСК+2 |
| [№0173200001426001991](https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0173200001426001991) | SUPERSEDED | 2026-10-14 00:00 | 2026-10-26 10:00 | МСК |
| [№0179200000126000015](https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0179200000126000015) | SCREENED_OUT | 2026-11-25 00:00 | 2026-11-30 18:00 | МСК |
| [№0339600002926000004](https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0339600002926000004) | FAILED | 2026-11-25 00:00 | 2026-11-26 04:00 | МСК+4 |
| [№0342200018726000064](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0342200018726000064) | MANAGER_READY | 2026-11-26 00:00 | 2026-11-25 23:00 | МСК+1 |
| [№0342200018726000064](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0342200018726000064) | DUPLICATE | 2026-11-26 00:00 | 2026-11-25 23:00 | МСК+1 |

## Подтверждённая точная полночь — не исправлять

- [№0133200003126000072](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0133200003126000072) — MANAGER_READY: 2026-11-26 00:00 МСК.
- [№0163200000326005984](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0163200000326005984) — MANAGER_READY: 2026-11-26 00:00 МСК.
- [№0163200000326005984](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0163200000326005984) — DUPLICATE: 2026-11-26 00:00 МСК.

## Ближайшие MANAGER_READY с будущими официальными сроками

| Извещение | ЕИС, МСК | БД, МСК | Сравнение |
|---|---|---|---|
| [№0853500000326008158](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0853500000326008158) | 2026-11-24 07:00 | 2026-11-24 00:00 | SAME_MSK_DATE_WRONG_CLOCK |
| [№0162300005326002146](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0162300005326002146) | 2026-11-24 08:00 | 2026-11-24 00:00 | SAME_MSK_DATE_WRONG_CLOCK |
| [№0137200001226009248](https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0137200001226009248) | 2026-11-25 08:00 | 2026-11-25 00:00 | SAME_MSK_DATE_WRONG_CLOCK |
| [№0318200064526000132](https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0318200064526000132) | 2026-11-25 08:00 | 2026-11-25 00:00 | SAME_MSK_DATE_WRONG_CLOCK |
| [№0342200018726000064](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0342200018726000064) | 2026-11-25 23:00 | 2026-11-26 00:00 | DIFFERENT_MSK_DATE |
| [№0133200003126000072](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0133200003126000072) | 2026-11-26 00:00 | 2026-11-26 00:00 | EXACT_MATCH |
| [№0163200000326005984](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0163200000326005984) | 2026-11-26 00:00 | 2026-11-26 00:00 | EXACT_MATCH |
| [№0112200000826005382](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0112200000826005382) | 2026-11-26 02:00 | 2026-11-26 00:00 | SAME_MSK_DATE_WRONG_CLOCK |
| [№0843500000226006859](https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0843500000226006859) | 2026-11-26 05:00 | 2026-11-26 00:00 | SAME_MSK_DATE_WRONG_CLOCK |
| [№0853500000326008327](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0853500000326008327) | 2026-11-26 07:00 | 2026-11-26 00:00 | SAME_MSK_DATE_WRONG_CLOCK |
| [№0137200001226009269](https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0137200001226009269) | 2026-11-26 08:00 | 2026-11-26 00:00 | SAME_MSK_DATE_WRONG_CLOCK |
| [№0114500000826002658](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0114500000826002658) | 2026-11-26 09:00 | 2026-11-26 00:00 | SAME_MSK_DATE_WRONG_CLOCK |
| [№0184200000626000970](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0184200000626000970) | 2026-11-26 09:00 | 2026-11-26 00:00 | SAME_MSK_DATE_WRONG_CLOCK |
| [№0190200000326013981](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0190200000326013981) | 2026-11-27 06:00 | 2026-11-27 00:00 | SAME_MSK_DATE_WRONG_CLOCK |
| [№0373400007726001146](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0373400007726001146) | 2026-11-27 07:00 | 2026-11-27 00:00 | SAME_MSK_DATE_WRONG_CLOCK |
| [№0142200001326022921](https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0142200001326022921) | 2026-11-27 09:00 | 2026-11-27 00:00 | SAME_MSK_DATE_WRONG_CLOCK |
| [№0179200001926000705](https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0179200001926000705) | 2026-11-27 09:00 | 2026-11-27 00:00 | SAME_MSK_DATE_WRONG_CLOCK |
| [№0373200007026000151](https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0373200007026000151) | 2026-11-27 09:00 | 2026-11-27 00:00 | SAME_MSK_DATE_WRONG_CLOCK |
| [№0119200000126021522](https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=0119200000126021522) | 2026-11-30 04:00 | 2026-11-30 00:00 | SAME_MSK_DATE_WRONG_CLOCK |
| [№0169300000326002843](https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0169300000326002843) | 2026-11-30 05:00 | 2026-11-30 00:00 | SAME_MSK_DATE_WRONG_CLOCK |

## Метод проверки

- 298 строк прочитаны из подтверждённой production PostgreSQL в одной транзакции REPEATABLE READ READ ONLY.
- Выполнено по одному публичному HTTPS GET на уникальный номер ЕИС (ea20, zk20, ok20) с проверкой исходного URL и номера. Дата и точное время извлечены из поля «Дата и время окончания срока подачи заявок» вместе с МСК±N.
- Первая попытка: 191/196, оставшиеся 5 (4 больших HTML, 1 временный timeout) успешно повторно проверены; исходные неудачные квитанции сохранены отдельно.
- Все 298 построчных сверок: EIS_298_ALL_VERIFIED.csv; SHA-256 CSV: c36168601f6b7b949002287d78363ad40bcfa3103cdd587466838e25353e2d3a. 196 HTML-оригиналов и квитанций хранятся приватно на Mac mini.

## Региональные пояса 196 исходных извещений

- МСК: 134
- МСК+1: 8
- МСК+2: 20
- МСК+3: 3
- МСК+4: 20
- МСК+5: 1
- МСК+6: 4
- МСК+7: 3
- МСК+8: 1
- МСК-1: 2
