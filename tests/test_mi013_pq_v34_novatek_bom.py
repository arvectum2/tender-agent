"""MI-013 v34 regression: secondary original board excerpt is not first-party award."""
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"/"market_intelligence"))
from materialize_pq_research_v34 import materialize
from export_pq_data_platform import export_records
from apply_pq_evidence_v34 import source_patch

class TestV34(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=materialize()
        cls.byid={r["canonical_id"]:r for r in cls.data["records"]}
        cls.row=cls.byid["commercial:ГП630876:lot1"]
        cls.patch=source_patch()

    def test_102_distinct_notices_still(self):
        self.assertEqual(len(self.byid),102)
        self.assertEqual(len(export_records(self.data)),102)
    def test_source_grade_stays_secondary(self):
        info=self.row["mi013_source_enrichments"]["v34"]
        self.assertEqual(info["source_grade"],"secondary_platform_reprint_not_primary_archive")
        self.assertFalse(self.patch["source_original_ETP_7z_files_verified"])
        self.assertFalse(self.patch["signed_contract_verified"])
        self.assertFalse(self.patch["supplier_name_verified"])
        self.assertIsNone(self.patch["hardware_only_price_rub"])
    def test_technical_quantities_are_components(self):
        s=self.patch["quantity_cross_checks"]
        self.assertEqual(s["switching_reactors_total"],8)
        self.assertEqual(s["fuses_total"],18)
        self.assertEqual(s["three_phase_capacitors_10p5kv_total"],1)
        self.assertEqual(self.patch["nominal_system_voltage_kv"],10)
        self.assertEqual(self.patch["separate_new_UKRM_sets_proven"],0)
        self.assertEqual(self.patch["source_board_visible_positions_count"],10)
    def test_no_signed_contract_or_oem(self):
        self.assertIsNone(self.patch["winning_offer_rub"])
        self.assertIsNone(self.patch["signed_contract_rub"])
        self.assertIsNone(self.patch["hardware_only_price_rub"])
    def test_first_party_original_2026_b2b_is_not_retrofit(self):
        b=self.byid["commercial:4643332:lot1"]
        self.assertEqual(b["original_bids_submitted"],0)
        self.assertEqual(b["equipment"]["nominal_voltage_kv"],10.5)
        self.assertNotEqual(b["customer"]["name"],self.row["customer"]["name"])

if __name__=="__main__":
    unittest.main()
