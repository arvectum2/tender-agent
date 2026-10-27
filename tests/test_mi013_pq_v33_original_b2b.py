"""MI-013 original 2026 B2B-Center 10.5kV capacitor corpus v33 safeguards."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"/"market_intelligence"))
from materialize_pq_research_v33 import materialize
from export_pq_data_platform import export_records
from import_pq_b2b_original_v33 import stage_one

class TestV33(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d=materialize()
        cls.rows=export_records(cls.d)
        cls.new=cls.d["records"][-1]

    def test_corpus_102_unique(self):
        self.assertEqual(len(self.rows),102)
        self.assertEqual(len({r["external_id"] for r in self.rows}),102)
        self.assertEqual(len({r["resource_id"] for r in self.rows}),102)

    def test_original_b2b_is_new_and_failed(self):
        r=self.new
        self.assertEqual(r["canonical_id"],"commercial:4643332:lot1")
        self.assertEqual(r["publication_date"],"2026-10-16")
        self.assertEqual(r["deadline_date"],"2026-10-19")
        self.assertEqual(r["original_bids_submitted"],0)
        self.assertIsNone(r["commission_winner"])
        self.assertIsNone(r["nmck_rub"])
        self.assertIsNone(r["actual_signed_contract_price_rub"])
        self.assertFalse(r["registered_signed_contract_verified"])

    def test_nominal_10p5kv_not_complete_statcom(self):
        r=self.new["equipment"]
        self.assertEqual(r["nominal_voltage_kv"],10.5)
        self.assertEqual(r["nameplate_kvar"],150)
        self.assertEqual(r["requested_units"],1)
        self.assertFalse(r["complete_ukrm"])
        self.assertFalse(r["installed_verified"])

    def test_organizer_differs_from_buyer(self):
        r=self.new
        self.assertEqual(r["organizer"]["name"],"ООО «УК «Колмар»")
        self.assertEqual(r["customer"]["inn"],"2709015787")
        self.assertEqual(r["buyer_original_label"],"АО «ВТУ»")

    def test_original_first_party_proof(self):
        r=self.new
        self.assertTrue(any(x["source_tier"]=="original_first_party_commercial_ETP" and
                            x["url"].startswith("https://www.b2b-center.ru/market/")
                            for x in r["evidence"]))
        self.assertEqual(stage_one()["content_hash"],self.rows[-1]["content_hash"])

    def test_v31_v32_no_duplication(self):
        cases={r["canonical_id"]:r for r in self.d["records"]}
        self.assertEqual(len(cases),102)
        self.assertIn("v31",cases["223fz:32413581034:lot2"]["mi013_source_enrichments"])
        self.assertIn("v32",cases["commercial:306-644:lot35"]["mi013_source_enrichments"])
        self.assertIn("v32",cases["223fz:32413708738:lot1"]["mi013_source_enrichments"])
        self.assertEqual(sum(bool(r.get("mi013_source_enrichments")) for r in cases.values()),15)

if __name__=="__main__":
    unittest.main()
