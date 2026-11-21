"""Local archived review CLI; no routes, production write or bid action."""
import argparse
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from src.modules.tender_operator_agent_demo.operator_cashflow_calendar import (
    CashCalendarRequest,
)
from src.modules.tender_operator_agent_demo.operator_cost_scenarios import (
    ExplicitCostScenarioRequest,
)
from src.modules.tender_operator_agent_demo.ri223_attachment_evidence import read_bytes
from src.modules.tender_operator_agent_demo.ri223_staged_calendar import (
    StagedRequest,
    review_staged_calendar,
    withholding_stress,
)


class WithholdingRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    calendar: CashCalendarRequest
    withheld_event_id: str=Field(pattern=r'^[A-Za-z0-9_-]{1,64}$')
    assumed_amount_rub: str=Field(pattern=r'^\d{1,12}(?:\.\d{1,2})?$')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run-id',required=True)
    p.add_argument('--scenario-json',type=Path,required=True)
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument('--staged-json',type=Path)
    group.add_argument('--withholding-json',type=Path)
    a=p.parse_args()
    cost=ExplicitCostScenarioRequest.model_validate_json(read_bytes(a.scenario_json,32768))
    if a.staged_json:
        req=StagedRequest.model_validate_json(read_bytes(a.staged_json,196608))
        out=review_staged_calendar(a.run_id,cost,req)
    else:
        req=WithholdingRequest.model_validate_json(read_bytes(a.withholding_json,196608))
        out=withholding_stress(a.run_id,cost,req.calendar,req.withheld_event_id,req.assumed_amount_rub)
    print(json.dumps(out,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
