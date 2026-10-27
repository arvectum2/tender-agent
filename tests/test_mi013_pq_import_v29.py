"""Source-scoped tests for the MI-013 v29 PostgreSQL importer.

No database changes; offline source staging plus optional live read-only preflight.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "market_intelligence"))
from import_pq_postgres_v29 import COLLECTION, materialize_v29, stage

class TestPQV29(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = materialize_v29()
        cls.rows = stage()
        cls.by_id = {r["external_id"]: r for r in cls.rows}

    def test_101_unique_stable_identifiers(self):
        self.assertEqual(len(self.by_id), 101)
        self.assertEqual(len({r["resource_id"] for r in self.rows}), 101)
        self.assertEqual(len({r["canonical_uri"] for r in self.rows}), 101)

    def test_no_elga_design_as_procurement(self):
        self.assertNotIn("engineering:2024:ps-elga-35-6kv-600kvar", self.by_id)

    def test_signed_contracts_never_invented_from_offers(self):
        for key in ["223fz:32514947144:lot1","223fz:32515029641:lot1","223fz:32515582393:lot1"]:
            row = self.by_id[key]["source_record"]["mi013_source_enrichments"]["v27"]["verified_original"]
            self.assertTrue(any("unverified" in str(z).lower() for z in row.values()) or
                            "sign" in json.dumps(row, ensure_ascii=False).lower())

    def test_v28_mixed_voltage_two_lots(self):
        for suffix in ("lot1", "lot2"):
            k = f"223fz:32616474682:{suffix}"
            self.assertIn("v28", self.by_id[k]["source_record"]["mi013_source_enrichments"])
        src = self.by_id["223fz:32616474682:lot1"]["source_record"]["mi013_source_enrichments"]["v28"]["verified_original"]
        self.assertEqual(src["total_low_voltage_piece_count"],26)
        self.assertEqual(src["total_medium_voltage_piece_count"],1)
        self.assertIsNone(src["actual_medium_voltage_component_price_rub"])

    def test_v23_distinct_notice_with_uncertain_framework_overlap(self):
        x=self.by_id["223fz:32616355390:lot1"]["source_record"]
        self.assertEqual(x["possible_duplicate_of"],"223fz:32515218366:lot1")
        self.assertTrue(x["excluded_from_market_value_aggregation"])
        self.assertIsNone(x["actual_revenue_rub"])

    def test_document_source_urls_and_staged_status(self):
        for r in self.rows:
            self.assertEqual(r["collection_id"],COLLECTION)
            self.assertEqual(r["status"],"staged_unreviewed")
            self.assertEqual(r["metadata"]["data_version"],"v29")
            self.assertTrue(r["metadata"]["research_not_market_population"])
            self.assertTrue(r["metadata"]["source_urls"])
            self.assertTrue(all(s.startswith("https://") for s in r["metadata"]["source_urls"]))

    def test_multi_version_enrichments(self):
        a=self.by_id["223fz:32515218366:lot1"]["source_record"]
        self.assertIn("v22",a["mi013_source_enrichments"])
        a=self.by_id["223fz:32616296475:lot1"]["source_record"]
        self.assertIn("v21",a["mi013_source_enrichments"])
        self.assertEqual(self.dataset["verification_summary"]["first_party_signed_contracts_known"],5)

    def test_missing_source_excluded_lot(self):
        ids=list(self.by_id)
        self.assertFalse(any("2024-mogocha-unverified" in x for x in ids))

if __name__=="__main__":
    unittest.main()
