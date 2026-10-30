"""Offline tests: run with `python tests/test_lex_th.py` from repo root."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from custom_components.lex_th import parse_response  # noqa: E402
from custom_components.lex_th.const import TRACKING_NUMBER_RE, normalize_status  # noqa: E402
from homeassistant.helpers.update_coordinator import UpdateFailed  # noqa: E402

REAL = {"success": True, "data": {
    "packageCode": "FU8220024300000000009266382621", "trackingNumber": "LEXPU0719633081",
    "status": "domestic_ib_success_in_sort_center", "firstMileShippingProvider": "LEX TH",
    "lastMileShippingProvider": "LEX TH", "destinationCountry": "TH",
    "timeline": [
        {"status": "domestic_pickup/sign_in_success", "processTime": 1793172386972,
         "shippingProvider": "LEX TH", "location": "บางเสาธง", "epod": "MASKED_EPOD"},
        {"status": "domestic_ib_success_in_sort_center", "processTime": 1793213631026,
         "shippingProvider": "LEX TH", "location": "บางเสาธง"},
    ]}}


class Tests(unittest.TestCase):
    def test_normalize(self):
        for raw, want in [
            ("domestic_ib_success_in_sort_center", "in_transit"),
            ("domestic_package_stationed_in", "in_transit"),
            ("package_ready_to_be_shipped", "ready_to_ship"),
            ("domestic_last_mile_customer_station_inbound", "awaiting_collection"),
            ("domestic_package_returned", "problem"),
            ("domestic_pickup/sign_in_success", "picked_up"),
            ("delivery_success", "delivered"),
            ("out_for_delivery", "out_for_delivery"),
            ("delivery_fail", "problem"),
            ("something_new", "unknown"),
            ("", "unknown"),
            (None, "unknown"),
        ]:
            self.assertEqual(normalize_status(raw), want, raw)

    def test_parse_real(self):
        d = parse_response("LEXPU0719633081", REAL)
        self.assertEqual(d["state"], "in_transit")
        self.assertEqual(len(d["timeline"]), 2)
        self.assertEqual(d["timeline"][0]["status"], "domestic_ib_success_in_sort_center")  # newest first
        self.assertEqual(d["last_location"], "บางเสาธง")
        self.assertEqual(d["last_update"].tzinfo.utcoffset(None).total_seconds(), 0)
        self.assertEqual(d["tracking_url"], "https://lex.th/tracking?references=LEXPU0719633081")

    def test_not_found(self):
        self.assertEqual(parse_response("X12345678", {"success": True})["state"], "not_found")

    def test_failure(self):
        with self.assertRaises(UpdateFailed):
            parse_response("X12345678", {"success": False})
        with self.assertRaises(UpdateFailed):
            parse_response("X12345678", None)

    def test_state_text_complete(self):
        from custom_components.lex_th.const import LANGUAGES, STATE_TEXT, STATES
        for lang in LANGUAGES:
            self.assertEqual(set(STATE_TEXT[lang]), set(STATES))

    def test_describe(self):
        from custom_components.lex_th.const import describe_status
        self.assertEqual(
            describe_status("domestic_ib_success_in_sort_center", "in_transit", "en"),
            "Package is being sorted and will soon head to the delivery facility",
        )
        self.assertIn("คัดแยก", describe_status("domestic_ib_success_in_sort_center", "in_transit", "th"))
        self.assertEqual(describe_status("delivery_success", "delivered", "en"), "Package has been delivered")
        self.assertEqual(describe_status(None, "unknown", "th"), "มีการอัปเดตสถานะพัสดุ")

    def test_all_official_codes(self):
        import json
        from custom_components.lex_th.const import RAW_STATUS, STATES
        self.assertEqual(len(RAW_STATUS), 43)
        root = Path(__file__).resolve().parents[1] / "custom_components" / "lex_th" / "translations"
        for lang in ("en", "th"):
            states = json.loads((root / f"{lang}.json").read_text(encoding="utf-8"))["entity"]["sensor"]["status"]["state"]
            self.assertEqual(set(states), set(STATES))
        for code, (state, en, th) in RAW_STATUS.items():
            self.assertIn(state, STATES, code)
            self.assertEqual(normalize_status(code), state, code)
            self.assertTrue(en and th, code)

    def test_unknown_shows_raw(self):
        from custom_components.lex_th.const import describe_status
        self.assertEqual(describe_status("zzz", "unknown", "en"), "Tracking update received (zzz)")

    def test_regex(self):
        self.assertTrue(TRACKING_NUMBER_RE.match("LEXPU0719633081"))
        self.assertFalse(TRACKING_NUMBER_RE.match("short"))
        self.assertFalse(TRACKING_NUMBER_RE.match("lowercase123"))


if __name__ == "__main__":
    unittest.main()
