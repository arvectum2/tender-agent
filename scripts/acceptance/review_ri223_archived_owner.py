"""Private local review; no API exposure, DB or submitted bid."""
import argparse
import json
from pathlib import Path

from src.modules.tender_operator_agent_demo.operator_cost_scenarios import (
    ExplicitCostScenarioRequest,
)
from src.modules.tender_operator_agent_demo.ri223_attachment_evidence import read_bytes
from src.modules.tender_operator_agent_demo.ri223_owner_review import (
    review_archived_owner_run,
)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--scenario-json',type=Path,help='Explicit what-if inputs')
    parser.add_argument("--decision",action="store_true",help="Combine original dossier and existing Decision Core")
    args=parser.parse_args()
    scenario=(ExplicitCostScenarioRequest.model_validate_json(read_bytes(args.scenario_json,32768))
              if args.scenario_json else None)
    print(json.dumps(review_archived_owner_run(args.run_id,scenario,include_decision=args.decision),ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
