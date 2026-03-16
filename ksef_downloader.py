#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from ksef_core import KsefClient, KsefConfig, save_documents, validate_config
from ksef_gui import run_gui


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="KSeF downloader - CLI + GUI")
    parser.add_argument("--gui", action="store_true", help="Uruchom interfejs graficzny")
    parser.add_argument("--base-url", help="Bazowy URL API KSeF")
    parser.add_argument("--nip", help="NIP podmiotu")
    parser.add_argument("--token", default=os.getenv("KSEF_TOKEN"), help="Token KSeF")
    parser.add_argument("--from-date", help="Data od (YYYY-MM-DD)")
    parser.add_argument("--to-date", help="Data do (YYYY-MM-DD)")
    parser.add_argument("--out-dir", default="./downloads", help="Katalog wyjściowy")
    parser.add_argument("--cert-type", choices=["pkcs12", "pem"], default="pkcs12")
    parser.add_argument("--cert-path", help="Ścieżka do certyfikatu .p12/.pfx")
    parser.add_argument("--cert-password", default=os.getenv("KSEF_CERT_PASSWORD"), help="Hasło certyfikatu")
    parser.add_argument("--cert-pem", help="Ścieżka do certyfikatu PEM")
    parser.add_argument("--key-pem", help="Ścieżka do klucza PEM")
    parser.add_argument("--insecure", action="store_true", help="Wyłącz weryfikację SSL")
    parser.add_argument("--debug", action="store_true", help="Włącz logi debug")
    return parser.parse_args()


def run_cli(args: argparse.Namespace) -> int:
    required = ["base_url", "nip", "from_date", "to_date"]
    missing = [name for name in required if not getattr(args, name)]
    if missing:
        raise SystemExit(f"Brak wymaganych parametrów CLI: {', '.join(missing)}. Użyj --gui albo podaj wszystkie opcje.")

    cfg = KsefConfig(
        base_url=args.base_url,
        nip=args.nip,
        token=args.token,
        out_dir=Path(args.out_dir),
        cert_type=args.cert_type,
        cert_path=Path(args.cert_path) if args.cert_path else None,
        cert_password=args.cert_password,
        cert_pem=Path(args.cert_pem) if args.cert_pem else None,
        key_pem=Path(args.key_pem) if args.key_pem else None,
        verify_ssl=not args.insecure,
    )

    validate_config(cfg)
    client = KsefClient(cfg)
    docs = client.list_documents(args.from_date, args.to_date)
    logging.info("Znaleziono dokumentów: %s", len(docs))

    saved = save_documents(client, docs, cfg.out_dir)
    logging.info("Pobrano i zapisano dokumentów: %s", saved)
    return 0


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    if args.gui:
        run_gui()
        return 0

    return run_cli(args)


if __name__ == "__main__":
    raise SystemExit(main())
