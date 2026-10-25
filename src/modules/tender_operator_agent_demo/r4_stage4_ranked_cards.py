"""Card-local failure isolation without shifting registered physical source ranks."""
from __future__ import annotations

from lxml import html

from src.modules.tender_operator_agent_demo.r4_stage3_crossvendor_cards import (
    MOS,
    SYNAPS,
    parse_stage3_cards,
)


def stage4_ranked_cards(*, source_index: int, original_html: bytes) -> list[dict]:
    """A malformed single Synaps card cannot create an unearned 44-FZ candidate."""
    if source_index in (3, 4):
        return parse_stage3_cards(MOS, original_html)
    if source_index not in (1, 2):
        raise ValueError("Unknown pre-registered stage4 source rank")
    root=html.fromstring(original_html)
    cards=root.xpath(
        '//div[contains(concat(" ",normalize-space(@class)," ")," sp-tender-block ")]'
    )
    if not 1<=len(cards)<=400:
        raise ValueError("Unverifiable Synaps source page layout")
    extracted=[]
    for i,card in enumerate(cards,1):
        # Serialize only the ONE source card with an explicit UTF-8 declaration.
        # The original HTML SHA was verified BEFORE this non-authoritative
        # helper is used for selecting candidate identities.
        data=(b'<html><head><meta charset="utf-8"></head><body>'
            +html.tostring(card,encoding="utf-8")
            +b'</body></html>')
        try:
            result=parse_stage3_cards(SYNAPS,data)
            if len(result)!=1:
                raise ValueError("Ambiguous card-local discovery result")
            row=dict(result[0])
        except ValueError:
            row={"law":"UNVERIFIABLE","registry_number":None}
        row["source_card_rank"]=i
        extracted.append(row)
    return extracted
