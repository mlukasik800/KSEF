import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ksef_core import (
    ClientProfile,
    KsefConfig,
    client_output_dir,
    create_zip_from_dir,
    delete_profile,
    extract_ksef_number,
    load_profiles,
    parse_and_validate_dates,
    safe_filename,
    upsert_profile,
    write_download_manifest,
    validate_config,
    validate_profile,
)


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

    def test_profiles_upsert_delete(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "clients.json"
            p = ClientProfile(name="Biuro Klient", nip="1234567890", bookkeeping_system="symfonia")
            validate_profile(p)
            upsert_profile(path, p)
            loaded = load_profiles(path)
            self.assertEqual(loaded[0].bookkeeping_system, "symfonia")
            out = client_output_dir(Path("/tmp/out"), p)
            self.assertIn("Biuro_Klient", str(out))
            delete_profile(path, "1234567890")
            self.assertEqual(load_profiles(path), [])

    def test_manifest_and_zip(self):
        with TemporaryDirectory() as tmpdir:
            from ksef_core import DownloadStats

            base = Path(tmpdir) / "out"
            base.mkdir()
            f1 = base / "a.xml"
            f1.write_text("<x/>", encoding="utf-8")
            profile = ClientProfile(name="A", nip="1234567890", bookkeeping_system="inne")
            stats = DownloadStats(total=1, saved=1, skipped=0, failed=0, saved_files=[f1])
            manifest = write_download_manifest(base, profile, stats)
            self.assertTrue(manifest.exists())
            zip_path = create_zip_from_dir(base, Path(tmpdir) / "pack.zip")
            self.assertTrue(zip_path.exists())



if __name__ == "__main__":
    unittest.main()
