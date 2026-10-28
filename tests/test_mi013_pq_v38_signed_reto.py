"""MI-013 v38 original registered 12 kV hardware supply safeguards."""
import sys,unittest
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"/"market_intelligence"))
from materialize_pq_research_v38 import materialize
from export_pq_data_platform import export_records
from import_pq_signed_reto_v38 import staged

class TestV38(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d=materialize()
        cls.rows=export_records(cls.d)
        cls.r=cls.d["records"][-1]
    def test_104_unique_source_notices(self):
        self.assertEqual(len(self.rows),104)
        self.assertEqual(len({x["external_id"] for x in self.rows}),104)
        self.assertEqual(len({x["resource_id"] for x in self.rows}),104)
    def test_signed_registry_original(self):
        x=self.r
        self.assertEqual(x["canonical_id"],"223fz:32616181358:lot1")
        self.assertEqual(x["registry_contract"]["registry_number"],"57724646338260000460000")
        self.assertTrue(x["registered_signed_contract_verified"])
        self.assertEqual(x["actual_signed_contract_price_rub"],"3050000.00")
        self.assertEqual(x["original_signed_contract_date"],"2026-08-19")
        self.assertEqual(x["status"],"registered_signed_contract_in_execution")
    def test_item_sum_and_voltage(self):
        x=self.r
        self.assertEqual(x["equipment"]["nominal_voltage_kv"],12)
        self.assertEqual(x["quantity"],10)
        self.assertEqual(sum(Decimal(y["unit_price_rub"])*int(y["units"]) for y in x["product_lines"]),Decimal("3050000"))
        self.assertEqual([y["model"] for y in x["product_lines"]],["КЭПФ-12-450-2УХЛ1","КЭПФ-12-600-2УХЛ1"])
        self.assertEqual(x["equipment"]["total_nameplate_kvar"],5250)
    def test_manufacturer_registration_not_origin_and_no_supplier_fabrication(self):
        x=self.r
        self.assertEqual(x["manufacturer_registered_country"],"Республика Казахстан")
        self.assertFalse(x["equipment"]["manufacturer_name_verified"])
        self.assertIsNone(x["supplier_inn"])
        self.assertFalse(x["supplier_verified"])
        self.assertFalse(x["delivered_verified"])
        self.assertFalse(x["paid_verified"])
    def test_original_eis_sources_replay_import(self):
        x=self.r
        self.assertEqual(len(x["evidence"]),2)
        self.assertTrue(all(y["url"].startswith("https://zakupki.gov.ru/epz/contractfz223/") for y in x["evidence"]))
        self.assertTrue(all(len(y["sha256"])==64 for y in x["evidence"]))
        self.assertEqual(staged()["content_hash"],self.rows[-1]["content_hash"])

if __name__=="__main__":unittest.main()
