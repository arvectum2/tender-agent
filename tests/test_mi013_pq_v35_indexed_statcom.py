"""v35 original-indexed Tender.Pro 2023 RMC four STATCOM request research-grade invariants."""
import sys,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"/"market_intelligence"))
from materialize_pq_research_v35 import materialize
from export_pq_data_platform import export_records
from import_pq_tenderpro_statcom_v35 import stage_one

class TestV35(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d=materialize()
        cls.out=export_records(cls.d)
        cls.r=cls.d["records"][-1]

    def test_count_and_unique(self):
        self.assertEqual(len(self.out),103)
        self.assertEqual(len({r["external_id"] for r in self.out}),103)
        self.assertEqual(len({r["resource_id"] for r in self.out}),103)

    def test_original_indexed_first_party_not_direct_verified(self):
        r=self.r
        self.assertEqual(r["canonical_id"],"commercial:834269:lot1")
        self.assertEqual(r["source_grade"],"original_ETP_public_page_cached_by_search_engine_not_directly_retrieved")
        self.assertIn("503",r["direct_first_party_http_result"])
        self.assertTrue(any(x["source_tier"]=="first_party_ETP_original_public_card_search_engine_indexed" for x in r["evidence"]))

    def test_six_to_thirtyfive_nominal_unconfirmed(self):
        r=self.r
        self.assertIsNone(r["equipment"]["nominal_voltage_kv"])
        self.assertIsNone(r["equipment"]["nameplate_kvar"])
        self.assertEqual(r["equipment"]["requested_units"],4)
        self.assertEqual(r["quantity"],4)
        self.assertIn("unknown",r["market_scope"])

    def test_not_a_signed_sale(self):
        r=self.r
        self.assertFalse(r["registered_signed_contract_verified"])
        self.assertIsNone(r["commission_winner"])
        self.assertIsNone(r["supplier_inn"])
        self.assertIsNone(r["actual_signed_contract_price_rub"])
        self.assertIsNone(r["nmck_rub"])

    def test_lot_two_same_procedure_not_a_second_procurement(self):
        r=self.r
        self.assertEqual(r["procedure_id"],"834269")
        self.assertTrue(r["associated_work_lot"]["same_procedure"])
        self.assertEqual(r["associated_work_lot"]["lot"],2)
        self.assertEqual(r["associated_work_lot"]["quantity"],1)
        self.assertEqual(stage_one()["content_hash"],self.out[-1]["content_hash"])

if __name__=="__main__":
    unittest.main()
