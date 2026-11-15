# GEH archival partitions and Moscow Portal paper-trading source pilot

## GEH

First-party published filters `procedure[accepted_from]` and `procedure[accepted_to]` use DD.MM.YYYY and constrain the application deadline in observed source cards. 2024 filter returned 11,202 offers; Jan–Oct 2025 returned 8,584 offers; both expose only 400 pages. Four actual monthly samples: Jan 2024 623/32 pages; Dec 2024 1,107/56; Oct 2025 993/50; Nov 2025 759/38. All first-page deadline dates within the corresponding interval. Capture separately as read-only source snapshots, verify count/page/hash/IDs, mark changed counts/duplicate IDs as review. Do not equate source counts with signed contracts or claim full market coverage.

## Moscow Portal

Published client JS SHA ca0a166667b3eb4059e304ed59ec673440a95a1e18eae547ece214672b7d94e8 and public settings SHA ccd49a81c4c0c4949315c4d8486db2b39070a8a2c768bdc5cbe07ad036647d20. Confirmed GET old.zakupki.mos.ru/api/Cssp/Purchase/Query, JSON queryDto, and GET zakupki.mos.ru/newapi/api/Auction/Get with auctionId. Finished state 19000004, canceled 19000005, failed 19000003, offers signed 19000008. These differ from legacy generic parser; do not apply them to other sources.

Public response reports 1,776,584 quote-session listing entries; selected finished/offers-signed filter reports 1,392,231. Four distinct details (10343271, 10343216, 10343235, 10343189), 43 positions, 28 distinct SKU, all initial position sums reconcile. All four have named winners/INN on list and consistent aggregate bid. No signed contract or winning SKU-level unit price proof. Exact source bytes saved in private runtime, SHA replay verified. Fresh list query yielded HTTP 400; seven detail attempts yielded HTTP 402; initial active detail returned HTTP 402. No attempt to evade access restrictions or buy data. Official developer access at https://zakupki.mos.ru/public-api-access requires further terms review. EAT loading/challenge not a verified data contract; TEK market JS is not a verified public procurement list. No production integration or automated trading claim.

Implementation: strict `mos_portal/public_auction.py`, bounded `capture_mos_public_auctions.py`, monthly `capture_gpb_history_partitions.py`. No mutations to TA/DP by these new scripts.
