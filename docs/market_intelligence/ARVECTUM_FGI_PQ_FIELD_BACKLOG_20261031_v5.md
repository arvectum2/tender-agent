# ARVECTUM — очередь доказательного заполнения карточек V5

Срез: 31.10.2026; 117 уникальных юридических лотов. Данные из read-only PostgreSQL snapshot V5.
Заполненное поле не всегда означает независимую верификацию. Участник комиссии ≠ победитель ≠ подписанный поставщик.

## Покрытие обязательных полей

| Поле | Заполнено | Отсутствует |
|---|---:|---:|
| `bid` | 5 | 112 |
| `buyer` | 116 | 1 |
| `buyer_inn` | 71 | 46 |
| `contract_date` | 9 | 108 |
| `contract_no` | 6 | 111 |
| `contract_price` | 10 | 107 |
| `date` | 113 | 4 |
| `description` | 117 | 0 |
| `equipment_only_price` | 1 | 116 |
| `family` | 117 | 0 |
| `id` | 117 | 0 |
| `nmck` | 44 | 73 |
| `platform` | 114 | 3 |
| `power` | 4 | 113 |
| `procedure` | 100 | 17 |
| `quantity` | 46 | 71 |
| `regime` | 117 | 0 |
| `scope` | 117 | 0 |
| `source_urls` | 105 | 12 |
| `status` | 117 | 0 |
| `voltage_kv` | 19 | 98 |
| `winner` | 3 | 114 |

## Очередь по каждому лоту

| Канонический ID | Класс | Заполнено | Следующее действие | Пробелы |
|---|:---:|---:|---|---|
| `223fz:32313008364:lot1` | C | 12/28 | P0/P1: identity and original source | buyer_inn, voltage_kv, power, quantity, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `223fz:32413195287:lot1` | A | 13/28 | P0/P1: identity and original source | buyer_inn, voltage_kv, power, quantity, bid, contract_price, equipment_only_price, paid_amount, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `223fz:32413581034:lot2` | C | 12/28 | P0/P1: identity and original source | platform, voltage_kv, power, quantity, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `223fz:32413708738:lot1` | C | 14/28 | P2: technical specification | power, quantity, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `223fz:32413764701:lot1` | A | 18/28 | P0/P1: identity and original source | date, quantity, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem |
| `223fz:32514476448:lot1` | C | 18/28 | P2: technical specification | power, bid, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem |
| `223fz:32514565977:lot1` | A | 15/28 | P2: technical specification | power, quantity, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `223fz:32514944142:lot1` | C | 13/28 | P2: technical specification | voltage_kv, power, quantity, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `223fz:32514947144:lot1` | C | 12/28 | P0/P1: identity and original source | buyer_inn, voltage_kv, power, quantity, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `223fz:32515029641:lot1` | C | 12/28 | P0/P1: identity and original source | buyer_inn, voltage_kv, power, quantity, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `223fz:32515044454:lot1` | C | 14/28 | P2: technical specification | voltage_kv, power, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `223fz:32515208744:lot1` | D | 11/28 | P0/P1: identity and original source | buyer_inn, source_urls, voltage_kv, power, quantity, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `223fz:32515218366:lot1` | C | 14/28 | P2: technical specification | voltage_kv, power, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `223fz:32515225588:lot1` | C | 12/28 | P0/P1: identity and original source | buyer_inn, voltage_kv, power, quantity, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `223fz:32515582393:lot1` | C | 14/28 | P2: technical specification | voltage_kv, power, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `223fz:32515584863:lot1` | D | 12/28 | P0/P1: identity and original source | source_urls, voltage_kv, power, quantity, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `223fz:32615614821:lot1` | B | 18/28 | P2: technical specification | power, bid, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem |
| `223fz:32615760238:lot1` | D | 12/28 | P0/P1: identity and original source | source_urls, voltage_kv, power, quantity, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `223fz:32615794236:lot1` | C | 17/28 | P2: technical specification | power, quantity, bid, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem |
| `223fz:32615852898:lot1` | C | 15/28 | P0/P1: identity and original source | buyer_inn, voltage_kv, power, bid, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_date |
| `223fz:32615937898:lot1` | D | 14/28 | P0/P1: identity and original source | source_urls, voltage_kv, quantity, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `223fz:32615966040:lot1` | C | 15/28 | P2: technical specification | voltage_kv, power, quantity, bid, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no |
| `223fz:32615969197:lot1` | B | 13/28 | P2: technical specification | voltage_kv, power, quantity, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `223fz:32616065155:lot7` | C | 13/28 | P0/P1: identity and original source | buyer_inn, voltage_kv, power, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `223fz:32616103025:lot1` | B | 13/28 | P2: technical specification | voltage_kv, power, quantity, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `223fz:32616120582:lot1` | B | 13/28 | P2: technical specification | voltage_kv, power, quantity, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `223fz:32616181358:lot1` | A | 14/28 | P2: technical specification | voltage_kv, power, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `223fz:32616266007:lot1` | A | 18/28 | P3: roles and protocol | contract_price, equipment_only_price, paid_amount, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `223fz:32616280467:lot1` | B | 14/28 | P2: technical specification | voltage_kv, power, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `223fz:32616296475:lot1` | C | 14/28 | P2: technical specification | voltage_kv, power, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `223fz:32616339168:lot1` | C | 13/28 | P2: technical specification | voltage_kv, power, quantity, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `223fz:32616354211:lot1` | C | 16/28 | P2: technical specification | voltage_kv, power, bid, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no |
| `223fz:32616355390:lot1` | A | 13/28 | P2: technical specification | voltage_kv, power, quantity, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `223fz:32616400421:lot1` | C | 13/28 | P2: technical specification | voltage_kv, power, quantity, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `223fz:32616412267:lot1` | B | 13/28 | P2: technical specification | voltage_kv, power, quantity, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `223fz:32616433248:lot1` | B | 14/28 | P2: technical specification | voltage_kv, power, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `223fz:32616435269:lot1` | C | 13/28 | P2: technical specification | voltage_kv, power, quantity, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `223fz:32616474682:lot1` | B | 14/28 | P2: technical specification | voltage_kv, power, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `223fz:32616474682:lot2` | B | 14/28 | P2: technical specification | voltage_kv, power, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `223fz:32616497692:lot1` | B | 17/28 | P3: roles and protocol | contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `223fz:32616506708:lot1` | C | 12/28 | P0/P1: identity and original source | platform, voltage_kv, power, quantity, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `223fz:chges24621PR:lot1` | C | 13/28 | P2: technical specification | voltage_kv, power, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `223fz:judicial-contract-03-34-24:lot1` | B | 17/28 | P0/P1: identity and original source | procedure, voltage_kv, power, nmck, bid, paid_amount, contract_signatory, supplier_inn, epc, designer, oem |
| `aggregator:2418411721:lot1` | D | 10/28 | P0/P1: identity and original source | procedure, buyer_inn, source_urls, power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:106044-ТТ:lot1` | C | 13/28 | P2: technical specification | voltage_kv, power, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:111098-ТТ:lot1` | C | 13/28 | P2: technical specification | voltage_kv, power, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:1148520:lot1` | C | 13/28 | P2: technical specification | voltage_kv, power, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:1190793:lot1` | C | 12/28 | P2: technical specification | voltage_kv, power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:119199-ТТ:lot1` | C | 13/28 | P2: technical specification | voltage_kv, power, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:1216754:lot1` | C | 11/28 | P0/P1: identity and original source | buyer_inn, voltage_kv, power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:1221629:lot1` | C | 13/28 | P2: technical specification | voltage_kv, power, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:1234013:lot1` | C | 12/28 | P2: technical specification | voltage_kv, power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:130233-ТТ:lot1` | C | 11/28 | P0/P1: identity and original source | buyer_inn, voltage_kv, power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:135171-ТТ:lot1` | C | 13/28 | P2: technical specification | voltage_kv, power, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:2103585-2:lot1` | D | 10/28 | P0/P1: identity and original source | buyer_inn, source_urls, voltage_kv, power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:2128160-1:lot1` | D | 10/28 | P0/P1: identity and original source | buyer_inn, source_urls, voltage_kv, power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:231994-2:lot1` | C | 12/28 | P2: technical specification | voltage_kv, power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:231994:lot1` | C | 12/28 | P2: technical specification | voltage_kv, power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:281-705:lot1` | A | 11/28 | P0/P1: identity and original source | buyer_inn, voltage_kv, power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:306-644:lot35` | B | 12/28 | P0/P1: identity and original source | buyer_inn, voltage_kv, power, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:351-062:lot1` | B | 12/28 | P0/P1: identity and original source | buyer_inn, voltage_kv, power, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:358-830:lot1` | B | 12/28 | P0/P1: identity and original source | buyer_inn, voltage_kv, power, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:364-959:lot1` | C | 11/28 | P0/P1: identity and original source | buyer_inn, voltage_kv, power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:4158439:lot1` | A | 11/28 | P0/P1: identity and original source | buyer_inn, voltage_kv, power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:4256170:lot1` | C | 13/28 | P2: technical specification | voltage_kv, power, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:4302914:lot1` | C | 12/28 | P2: technical specification | voltage_kv, power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:4304120:lot1` | C | 13/28 | P2: technical specification | voltage_kv, power, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:4526968:lot1` | C | 13/28 | P2: technical specification | voltage_kv, power, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:4535313:lot1` | C | 13/28 | P0/P1: identity and original source | buyer_inn, power, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:4559984:ukrm-6p3-component` | C | 14/28 | P2: technical specification | power, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:4561228:lot1` | C | 14/28 | P2: technical specification | power, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:4561243:lot1` | C | 14/28 | P2: technical specification | power, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:4565274:lot1` | C | 14/28 | P2: technical specification | power, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:4617521:lot1` | A | 11/28 | P0/P1: identity and original source | buyer_inn, voltage_kv, power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:4643332:lot1` | B | 13/28 | P2: technical specification | voltage_kv, power, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:4657777:lot1` | A | 12/28 | P0/P1: identity and original source | buyer_inn, voltage_kv, power, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:5534/1866-УДСН:lot1` | D | 10/28 | P0/P1: identity and original source | buyer_inn, date, source_urls, power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:5631/018-Ял:lot1` | D | 9/28 | P0/P1: identity and original source | buyer_inn, date, source_urls, voltage_kv, power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:5747901:lot1` | C | 13/28 | P2: technical specification | voltage_kv, power, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:77795100:lot1` | C | 11/28 | P0/P1: identity and original source | buyer_inn, voltage_kv, power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:77907981:lot1` | C | 11/28 | P0/P1: identity and original source | buyer_inn, voltage_kv, power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:834269:lot1` | B | 11/28 | P0/P1: identity and original source | buyer, buyer_inn, voltage_kv, power, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:86829457:lot1` | C | 11/28 | P0/P1: identity and original source | buyer_inn, voltage_kv, power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:895449:lot1` | C | 13/28 | P2: technical specification | voltage_kv, power, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:945712:lot1` | C | 13/28 | P2: technical specification | voltage_kv, power, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:COM07102500074:lot1` | C | 12/28 | P2: technical specification | voltage_kv, power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:COM16012600053:lot1` | C | 12/28 | P2: technical specification | voltage_kv, power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:COM20082600016:lot1` | C | 12/28 | P2: technical specification | voltage_kv, power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:RAD260049805:lot1` | C | 14/28 | P2: technical specification | power, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:UKK-0SCS-3-102:lot1` | D | 11/28 | P0/P1: identity and original source | source_urls, voltage_kv, power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:unverified-rosneft-2025-02-28-ukrm6kv-blockbox:lot1` | C | 10/28 | P0/P1: identity and original source | procedure, buyer_inn, voltage_kv, power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:unverified-suhodol-2025-07-17:lot1` | C | 11/28 | P0/P1: identity and original source | procedure, buyer_inn, voltage_kv, power, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:АП125337:lot1` | C | 13/28 | P2: technical specification | voltage_kv, power, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:ГП630876:lot1` | C | 14/28 | P2: technical specification | power, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:РН41205245:lot1` | C | 12/28 | P2: technical specification | voltage_kv, power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:РН50303773:lot1` | C | 11/28 | P0/P1: identity and original source | buyer_inn, voltage_kv, power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:РН51202455:lot1` | C | 12/28 | P2: technical specification | voltage_kv, power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:РН60802401:lot1` | C | 11/28 | P0/P1: identity and original source | buyer_inn, voltage_kv, power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:РН60804549:lot1` | C | 11/28 | P0/P1: identity and original source | buyer_inn, voltage_kv, power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:РН61001644:lot1` | C | 11/28 | P0/P1: identity and original source | buyer_inn, voltage_kv, power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:РН61003961:lot1` | A | 13/28 | P2: technical specification | power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:РН61004155:lot1` | C | 12/28 | P2: technical specification | voltage_kv, power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `commercial:РН61005187:lot1` | C | 11/28 | P0/P1: identity and original source | buyer_inn, voltage_kv, power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `index:energybase:rosneft-pq-20231109-kharampur` | C | 10/28 | P0/P1: identity and original source | procedure, buyer_inn, voltage_kv, power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `index:energybase:rosneft-pq-20231201-kharampur` | C | 10/28 | P0/P1: identity and original source | procedure, buyer_inn, voltage_kv, power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `index:energybase:rosneft-pq-20240124-rospan` | C | 10/28 | P0/P1: identity and original source | procedure, buyer_inn, voltage_kv, power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `index:energybase:rosneft-pq-20240320-bashneft-polyus` | C | 10/28 | P0/P1: identity and original source | procedure, buyer_inn, voltage_kv, power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `index:energybase:rosneft-pq-20240411-kharampur` | C | 10/28 | P0/P1: identity and original source | procedure, buyer_inn, voltage_kv, power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `index:energybase:rosneft-pq-20240423-kharampur` | C | 10/28 | P0/P1: identity and original source | procedure, buyer_inn, voltage_kv, power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `index:energybase:rosneft-pq-20240427-nizhnevartovsk` | C | 10/28 | P0/P1: identity and original source | procedure, buyer_inn, voltage_kv, power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `index:energybase:rosneft-pq-20240517-kharampur-nku` | C | 10/28 | P0/P1: identity and original source | procedure, buyer_inn, voltage_kv, power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `index:energybase:rosneft-pq-20250410-rospan-ktp-ukrm` | C | 10/28 | P0/P1: identity and original source | procedure, buyer_inn, voltage_kv, power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `index:rostender:88416730` | C | 11/28 | P0/P1: identity and original source | procedure, buyer_inn, power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `index:vsempodryad:9d4a58cf-6c10-4485-8537-53e550c24269` | C | 13/28 | P0/P1: identity and original source | procedure, platform, voltage_kv, power, quantity, bid, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no |
| `index:vsempodryad:ea5a381b-31b1-4c37-962f-9fddf1761b74` | D | 14/28 | P0/P1: identity and original source | procedure, source_urls, voltage_kv, power, bid, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no |
| `index:vsempodryad:tplus-samara-gres-reactive-20240427` | D | 8/28 | P0/P1: identity and original source | procedure, buyer_inn, date, source_urls, voltage_kv, power, quantity, nmck, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |
| `platform:1351/ОАЭ-ЦДКС/26:lot1` | C | 13/28 | P2: technical specification | voltage_kv, power, quantity, bid, contract_price, equipment_only_price, paid_amount, winner, contract_signatory, supplier_inn, epc, designer, oem, contract_no, contract_date |

## Подтверждение по кейсу 32616497692

П2: 10,5 кВ и 3150 кВАр из оригинального DOCX; P3: участник №1 и предложение 79 101 498,40 ₽ из оригинального RTF переторжки. Подписанный договор и победитель не доказаны.
Цена относится к общему EPC (две подстанции), не к отдельно проданному оборудованию PQ.
Источники SHA: 66f2dec7487352c6bba4e7f5f182a3e2a614c7310dfec9ac2b9e82ed87d7c834 и c6fb6317471d1bc0fff40d641152df09cacd734e188a4f12eb73153898eddbbb.
