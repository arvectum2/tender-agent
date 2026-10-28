"""Primary EIS original 2026 Rosseti BSK mixed capacitor procurement source safeguards."""
import sys,unittest
from decimal import Decimal
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"/"market_intelligence"))
from materialize_pq_research_v37 import materialize
from export_pq_data_platform import export_records
from apply_pq_evidence_v37 import source_patch

class TestV37(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p=source_patch()
        cls.d=materialize()
        cls.rows=export_records(cls.d)

    def test_all_103_and_existing_canonical(self):
        self.assertEqual(len(self.rows),103)
        self.assertEqual(len({x["external_id"] for x in self.rows}),103)
        match=[x for x in self.d["records"] if x["canonical_id"]=="223fz:32616339168:lot1"]
        self.assertEqual(len(match),1)
        self.assertIn("v37",match[0]["mi013_source_enrichments"])

    def test_third_voltage_below_target(self):
        a=self.p["original_archived_technical"]["items"]
        self.assertEqual([(x["voltage_kv"],x["quantity"]) for x in a],[(12,12),(11.55,6),(4.2,6)])
        self.assertEqual(sum(x["quantity"] for x in a if x["strict_6_to_35kv"]),18)
        self.assertEqual(sum(x["quantity"] for x in a),24)
        self.assertFalse(self.p["original_archived_technical"]["nominal_voltage_of_substation_bus_verified"])

    def test_technical_item_quote_total_and_strict_subset(self):
        a=self.p["original_price_sources"]
        self.assertEqual(sum(Decimal(x["chosen_initial_estimate_total_inc_vat22_rub"]) for x in a),Decimal("6807600.00"))
        self.assertEqual(sum(Decimal(x["chosen_initial_estimate_total_inc_vat22_rub"]) for x in a if x["strict_6_to_35kv"]),Decimal("5286000.00"))
        self.assertEqual(sum(Decimal(x["chosen_initial_estimate_total_ex_vat_rub"]) for x in a),Decimal("5580000.00"))
        self.assertEqual([x["selected_price_individual_inc_vat22_rub"] for x in a],["275000.00","303000.00","253600.00"])
        self.assertEqual(len(self.p["original_quotation_sources"]),3)

    def test_1875_preference_not_meles_limitation(self):
        for x in self.p["original_archived_technical"]["items"]:
            self.assertEqual(x["PP1875"],"преимущество")
        self.assertEqual(self.p["original_archived_technical"]["items"][0]["source_code"],"27.90.52.000")

    def test_source_checksums_and_no_fake_award(self):
        s=self.p["original_sources"]
        self.assertEqual(len(s),5)
        self.assertTrue(all(len(x["sha256"])==64 for x in s))
        self.assertTrue(s[0]["url"].startswith("https://zakupki.gov.ru/223/filestore"))
        self.assertFalse(self.p["original_signed_contract_verified"])
        self.assertIsNone(self.p["winning_supplier"])
        self.assertIsNone(self.p["actual_paid_amount_rub"])

if __name__=="__main__": unittest.main()
