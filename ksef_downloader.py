#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from ksef_core import (
    BOOKKEEPING_SYSTEMS,
    ClientProfile,
    KsefClient,
    KsefConfig,
    client_output_dir,
    parse_and_validate_dates,
    create_zip_from_dir,
    save_documents,
    upsert_profile,
    write_download_manifest,
    validate_config,
    validate_profile,
)
from ksef_gui import run_gui


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="KSeF downloader - pobieranie i zarządzanie klientami")
    p.add_argument("--gui", action="store_true")
    p.add_argument("--client-name")
    p.add_argument("--client-nip")
    p.add_argument("--bookkeeping-system", choices=list(BOOKKEEPING_SYSTEMS), default="inne")
    p.add_argument("--profiles-path", default="./clients.json")
    p.add_argument("--save-client", action="store_true")

    p.add_argument("--base-url")
    p.add_argument("--nip")
    p.add_argument("--token", default=os.getenv("KSEF_TOKEN"))
    p.add_argument("--from-date")
    p.add_argument("--to-date")
    p.add_argument("--out-dir", default="./downloads")
    p.add_argument("--cert-type", choices=["pkcs12", "pem"], default="pkcs12")
    p.add_argument("--cert-path")
    p.add_argument("--cert-password", default=os.getenv("KSEF_CERT_PASSWORD"))
    p.add_argument("--cert-pem")
    p.add_argument("--key-pem")
    p.add_argument("--insecure", action="store_true")
    p.add_argument("--page-size", type=int, default=100)
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--zip-output", action="store_true", help="Spakuj pobrane XML + manifest do ZIP")
    p.add_argument("--debug", action="store_true")
    return p.parse_args()


def run_cli(args: argparse.Namespace) -> int:
    for req in ("base_url", "from_date", "to_date"):
        if not getattr(args, req):
            raise SystemExit(f"Brak wymaganego parametru: --{req.replace('_', '-')}")
    if args.page_size <= 0:
        raise SystemExit("--page-size musi być > 0")

    effective_nip = args.client_nip or args.nip
    if not effective_nip:
        raise SystemExit("Podaj --nip lub --client-nip")

    profile = ClientProfile(
        name=args.client_name or f"Klient_{effective_nip}",
        nip=effective_nip,
        bookkeeping_system=args.bookkeeping_system,
    )
    validate_profile(profile)
    if args.save_client:
        upsert_profile(Path(args.profiles_path), profile)

    cfg = KsefConfig(
        base_url=args.base_url,
        nip=effective_nip,
        token=args.token,
        out_dir=client_output_dir(Path(args.out_dir), profile),
        cert_type=args.cert_type,
        cert_path=Path(args.cert_path) if args.cert_path else None,
        cert_password=args.cert_password,
        cert_pem=Path(args.cert_pem) if args.cert_pem else None,
        key_pem=Path(args.key_pem) if args.key_pem else None,
        verify_ssl=not args.insecure,
    )

    validate_config(cfg)
    parse_and_validate_dates(args.from_date, args.to_date)
    client = KsefClient(cfg)
    docs = client.list_documents(args.from_date, args.to_date, page_size=args.page_size)
    stats = save_documents(client, docs, cfg.out_dir, overwrite=args.overwrite)
    manifest_path = write_download_manifest(cfg.out_dir, profile, stats)
    logging.info("Zapisano manifest: %s", manifest_path)

    if args.zip_output:
        zip_path = cfg.out_dir.parent / f"{cfg.out_dir.name}.zip"
        create_zip_from_dir(cfg.out_dir, zip_path)
        logging.info("Utworzono paczkę ZIP: %s", zip_path)

    logging.info("Klient=%s NIP=%s zapisane=%s pominięte=%s błędy=%s katalog=%s", profile.name, profile.nip, stats.saved, stats.skipped, stats.failed, cfg.out_dir)
    return 0


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    if args.gui:
        run_gui()
        return 0
    return run_cli(args)


if __name__ == "__main__":
    raise SystemExit(main())
