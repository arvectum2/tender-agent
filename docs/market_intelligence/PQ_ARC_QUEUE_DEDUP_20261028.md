# ARC ChatGPT source-review queue — SHA-level duplicate avoidance (28 October 2026)

Task: TA-MI-AUTONOMY-20261027. The queue contains multiple source-folder packets for the same official notice. Re-reviewing identical original SHA-256 documents is unnecessary, but a pending packet containing any **new** source SHA must remain reviewable.

The read-only `pq_arc_chat next` selector now skips pending packets only when **all** of their source SHA values are covered by an already-reviewed packet with the **same exact registry number**. It does not alter queue state or review history, and it does not skip packets with additional distinct original SHA. A regression test covers duplicate-only and new-document cases.

For notice **32414141662**, a second packet contained additional original documents, including the SHA-bound 110 kV technical specification `964dba8b49b77a6ed4ee1c0985be8453ef039f7868c8c826ae6ee94e2f5295d0`. ChatGPT in this run verified the exact quote «Технические характеристики и требования к комплекту оборудования источника реактивной мощности 110 кВ» and accepted packet `32414141662-14b19c48dfe0283628072ff0` as **irrelevant** to the 6–35 kV market. This is not evidence of an executed contract or supplier.

After acceptance, `pq_arc_chat next` returned **empty** with **two unreadable original-text packets** and **two exact-SHA duplicate packets** skipped. Durable queue states: 86 reviewed, 4 pending (2 unreadable and 2 already-source-covered). No OCR was promoted, and no previous reviewed packet was overwritten.

Next: preserve the two unreadable originals for a separately source-bound visual review; do not infer technical voltage or award from OCR alone. For duplicate-only packets, keep audit records without repeated ChatGPT classification. Continue official original evidence recovery and calendar-scoped EIS/ETP searches. Data Platform SDK remains blocked pending authorized key.
