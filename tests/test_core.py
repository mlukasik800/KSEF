import unittest
from pathlib import Path

from ksef_core import KsefConfig, extract_ksef_number, parse_and_validate_dates, safe_filename, validate_config


class TestCoreHelpers(unittest.TestCase):
    def test_parse_and_validate_dates_ok(self):
        parse_and_validate_dates("2025-01-01", "2025-01-31")

    def test_parse_and_validate_dates_invalid_order(self):
        with self.assertRaises(ValueError):
            parse_and_validate_dates("2025-02-01", "2025-01-31")

    def test_safe_filename(self):
        self.assertEqual(safe_filename("A/B:C*D"), "A_B_C_D")

    def test_extract_ksef_number(self):
        self.assertEqual(extract_ksef_number({"ksefReferenceNumber": "ABC"}), "ABC")
        self.assertIsNone(extract_ksef_number({"x": "y"}))

    def test_validate_config(self):
        cfg = KsefConfig(
            base_url="https://ksef.mf.gov.pl",
            nip="1234567890",
            token="token",
            out_dir=Path("./downloads"),
            cert_type="pkcs12",
            cert_path=Path("/tmp/cert.p12"),
        )
        validate_config(cfg)


if __name__ == "__main__":
    unittest.main()
