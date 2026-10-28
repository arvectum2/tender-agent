"""MI013 v40: original EIS 35kV EPC commission does NOT evidence signed UKRM sale."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"/"market_intelligence"))
from materialize_pq_research_v40 import materialize
from export_pq_data_platform import export_records
from apply_pq_karelia_commission_v40 import proof

class TestV40(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d=materialize()
        cls.p=proof()
    def test_104_source_notices_not_new_case(self):
        a=export_records(self.d)
        self.assertEqual(len(a),104)
        self.assertEqual(len({x["external_id"] for x in a}),104)
    def test_both_original_protocols(self):
        self.assertEqual(self.p["preliminary_protocol"]["signed_date"],"2026-10-14")
        self.assertEqual(self.p["final_protocol"]["signed_date"],"2026-10-19")
        self.assertEqual(len(self.p["preliminary_protocol"]["original_archive"]["sha256"]),64)
        self.assertEqual(len(self.p["final_protocol"]["original_archive"]["sha256"]),64)
    def test_one_bid_no_reduction_and_no_signed_contract(self):
        self.assertEqual(self.p["final_protocol"]["bids_received"],1)
        self.assertFalse(self.p["final_protocol"]["retender_price_reduced"])
        self.assertTrue(self.p["final_protocol"]["procurement_legally_failed_one_bid"])
        self.assertFalse(self.p["signed_original_rd223_contract_verified"])
    def test_epc_amount_not_hardware_sale(self):
        self.assertEqual(self.p["full_epc_total_nmc_rub"],"56330673.93")
        self.assertTrue(self.p["full_epc_cost_is_not_ukrm_price"])
        self.assertEqual(self.p["equipment"]["units_requested"],1)
        self.assertIsNone(self.p["equipment"]["hardware_only_signed_price_rub"])
    def test_secondary_name_not_primary_winner(self):
        self.assertEqual(self.p["second_tier_bidder"]["inn"],"7801564611")
        self.assertFalse(self.p["second_tier_bidder"]["verified_primary_legal_person"])
        self.assertIsNone(self.p["final_protocol"].get("bidder_name_original"))
        self.assertEqual(self.d["verification_summary"]["original_first_party_registered_signed_contracts"],6)

if __name__=="__main__":unittest.main()
