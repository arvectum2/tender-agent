"""Offline safeguards for two MI-013 v32 original procurement source updates."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"/"market_intelligence"))
from apply_pq_evidence_v32 import evidence, TARGETS


class TestMI013V32(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = evidence()
        cls.s = cls.d["commercial:306-644:lot35"]
        cls.t = cls.d["223fz:32413708738:lot1"]

    def test_exactly_two_existing_notices(self):
        self.assertEqual(set(self.d),TARGETS)

    def test_buyer_owned_6kv_not_new_equipment_sale(self):
        p=self.s
        self.assertTrue(p["original_buyers_device_provided"])
        self.assertEqual(p["original_technical"]["devices_to_install"],2)
        self.assertEqual(p["original_technical"]["each_voltage_kv"],6)
        self.assertEqual(p["original_technical"]["each_power_kvar"],900)
        self.assertEqual(p["original_technical"]["total_power_kvar"],1800)
        self.assertEqual(p["hardware_new_sale_count"],0)
        self.assertIsNone(p["signed_amount_rub"])

    def test_failed_2024_turan_220kv_not_awarded(self):
        p=self.t
        self.assertEqual(p["original_submitted_bids"],2)
        self.assertEqual(p["original_admitted_bids"],0)
        self.assertEqual(p["original_rejected_bids"],2)
        self.assertIsNone(p["winner"])
        self.assertEqual(len(p["named_original_bidders"]),2)
        self.assertTrue(all(x["commission_outcome"]=="rejected" for x in p["named_original_bidders"]))
        self.assertFalse(p["original_registered_signed_contract_verified"])
        self.assertFalse(p["target_voltage_6_35kV_device_in_lot_verified"])

    def test_original_sources_sha256_and_no_price_fabrication(self):
        for p in self.d.values():
            self.assertTrue(p["evidence"])
            for item in p["evidence"]:
                self.assertTrue(item["url"].startswith("https://"))
                if item.get("sha256"):
                    self.assertEqual(len(item["sha256"]),64)
                    self.assertTrue(all(x in "0123456789abcdef" for x in item["sha256"]))
        self.assertEqual(self.t["nmc_inc_vat20_rub"],"826223180.00")
        self.assertIsNone(self.t["actual_signed_contract_price_rub"])
        self.assertIsNone(self.s["signed_amount_rub"])

if __name__=="__main__":
    unittest.main()
