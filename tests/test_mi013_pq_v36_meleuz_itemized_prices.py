"""MI-013 v36 first-party ETP itemized medium-voltage PQ equipment estimate tests."""
import sys,unittest,hashlib
from decimal import Decimal
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"/"market_intelligence"))
from materialize_pq_research_v36 import materialize
from export_pq_data_platform import export_records
from apply_pq_evidence_v36 import source_patch

class TestV36(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d=materialize()
        cls.p=source_patch()
        cls.ledger=export_records(cls.d)

    def test_preserve_103_notices_one_updated_original(self):
        self.assertEqual(len(cls:=self.ledger),103)
        self.assertEqual(len({x["external_id"] for x in cls}),103)
        a=next(r for r in self.d["records"] if r["canonical_id"]=="223fz:32616296475:lot1")
        self.assertIn("v21",a["mi013_source_enrichments"])
        self.assertIn("v36",a["mi013_source_enrichments"])

    def test_source_grade_and_hashes(self):
        a=self.p["original_source_files"]
        self.assertEqual(len(a),4)
        self.assertEqual(sum(x["tier"].startswith("first_party_original") for x in a),4)
        for file in a:
            self.assertTrue(file["url"].startswith("https://zakaz.etp-region.ru/"))
            self.assertEqual(len(file["sha256"]),64)
            self.assertTrue(all(c in "0123456789abcdef" for c in file["sha256"]))

    def test_three_prices_separate_hardware_from_supervisory_and_pnr(self):
        p=self.p["original_price_justification"]
        lines=p["units_and_article_quantities"]
        self.assertEqual([x["class"] for x in lines],[
            "strict_6_35kv_equipment_only_benchmark",
            "separate_supervisory_installation_service","separate_commissioning_service"])
        self.assertEqual([x["buyer_line_average_rub"] for x in lines],
                         ["3524107.07","252333.33","128333.33"])
        self.assertEqual(sum(Decimal(x["buyer_line_average_rub"]) for x in lines),
                         Decimal("3904773.73"))
        for k in range(3):
            self.assertEqual(sum(Decimal(x["offers_rub"][k]) for x in lines),
                             Decimal(p["total_per_reference_rub"][k]))
        self.assertEqual(p["estimate_vat_inclusion"].startswith("NOT DETERMINABLE"),True)

    def test_1875_is_limitation_not_prohibition(self):
        legal=self.p["national_origin_procurement_restriction"]
        self.assertEqual(legal["original_table_cell_tick_location"],"Ограничение")
        self.assertFalse(legal["is_checkbox_under_prohibition"])
        self.assertTrue(legal["is_checkbox_under_limitation"])

    def test_technical_scope_and_no_fake_contract(self):
        t=self.p["original_technical"]
        self.assertEqual(t["nominal_network_voltage_max_kv"],6.3)
        self.assertEqual(t["nominal_reactive_power_min_kvar"],500)
        self.assertEqual(t["management_time_response_max_ms"],5)
        self.assertEqual(t["cabinet_IP_min"],"IP54")
        self.assertEqual(t["assembly_by"],"BUYER SELF (not supplier's full erection)")
        self.assertFalse(self.p["contractual_scope"]["original_signed_contract_verified"])
        self.assertIsNone(self.p["contractual_scope"]["actual_signed_contract_total_rub"])
        self.assertIsNone(self.p["original_price_justification"]["actual_paid_price"])

if __name__=="__main__":
    unittest.main()
