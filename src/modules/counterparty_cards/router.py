from fastapi import APIRouter

from src.modules.counterparty_cards.schemas import CounterpartyCardResponse
from src.modules.counterparty_cards.service import (
    get_customer_counterparty_card,
    get_supplier_counterparty_card,
)
from src.shared.api.dependencies import DBSession

router = APIRouter(prefix="/counterparties", tags=["counterparties"])


@router.get("/customers/{customer_id}", response_model=CounterpartyCardResponse)
def get_customer_counterparty_card_route(
    customer_id: str,
    session: DBSession,
) -> CounterpartyCardResponse:
    return get_customer_counterparty_card(session, customer_id)


@router.get("/suppliers/{supplier_id}", response_model=CounterpartyCardResponse)
def get_supplier_counterparty_card_route(
    supplier_id: str,
    session: DBSession,
) -> CounterpartyCardResponse:
    return get_supplier_counterparty_card(session, supplier_id)
