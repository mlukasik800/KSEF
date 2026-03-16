from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

try:
    from requests_pkcs12 import Pkcs12Adapter  # type: ignore
except Exception:  # pragma: no cover
    Pkcs12Adapter = None

LOGGER = logging.getLogger("ksef-downloader")


@dataclass
class KsefConfig:
    base_url: str
    nip: str
    token: str
    out_dir: Path
    cert_type: str = "pkcs12"
    cert_path: Optional[Path] = None
    cert_password: Optional[str] = None
    cert_pem: Optional[Path] = None
    key_pem: Optional[Path] = None
    verify_ssl: bool = True


class KsefClient:
    def __init__(self, cfg: KsefConfig, timeout: int = 60) -> None:
        self.cfg = cfg
        self.timeout = timeout
        self.session = self._build_session()

    def _build_session(self):
        try:
            import requests
        except ModuleNotFoundError as exc:
            raise RuntimeError("Brak biblioteki requests. Zainstaluj zależności z requirements.txt") from exc

        session = requests.Session()
        session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.cfg.token}",
                "NIP": self.cfg.nip,
            }
        )

        if self.cfg.cert_type == "pkcs12":
            if Pkcs12Adapter is None:
                raise RuntimeError("Brak biblioteki requests-pkcs12. Zainstaluj dependencies.")
            if not self.cfg.cert_path:
                raise ValueError("Dla cert_type=pkcs12 wymagany jest --cert-path")
            session.mount(
                "https://",
                Pkcs12Adapter(
                    pkcs12_filename=str(self.cfg.cert_path),
                    pkcs12_password=self.cfg.cert_password or "",
                ),
            )
        elif self.cfg.cert_type == "pem":
            if not self.cfg.cert_pem or not self.cfg.key_pem:
                raise ValueError("Dla cert_type=pem wymagane są --cert-pem i --key-pem")
            session.cert = (str(self.cfg.cert_pem), str(self.cfg.key_pem))
        else:
            raise ValueError("Nieobsługiwany cert_type. Użyj: pkcs12 albo pem.")

        session.verify = self.cfg.verify_ssl
        return session

    def list_documents(self, from_date: str, to_date: str, page_size: int = 100) -> List[Dict[str, Any]]:
        documents: List[Dict[str, Any]] = []
        page = 1

        while True:
            payload = {
                "queryCriteria": {
                    "invoiceDateFrom": from_date,
                    "invoiceDateTo": to_date,
                },
                "pageSize": page_size,
                "pageOffset": (page - 1) * page_size,
            }
            url = f"{self.cfg.base_url.rstrip('/')}/api/online/Query/Invoice/Sync"
            LOGGER.info("Pobieram listę dokumentów: strona=%s", page)
            response = self.session.post(url, data=json.dumps(payload), timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            page_docs = data.get("invoices") or data.get("elements") or []
            if not page_docs:
                break

            documents.extend(page_docs)
            if len(page_docs) < page_size:
                break
            page += 1

        return documents

    def download_document_xml(self, ksef_number: str) -> bytes:
        url = f"{self.cfg.base_url.rstrip('/')}/api/online/Invoice/Get/{ksef_number}"
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()

        ctype = response.headers.get("Content-Type", "")
        if "application/json" in ctype.lower():
            payload = response.json()
            raw = payload.get("invoice") or payload.get("xml") or ""
            return raw.encode("utf-8")

        return response.content


def validate_config(cfg: KsefConfig) -> None:
    if not cfg.token:
        raise ValueError("Brak tokenu KSeF.")
    if not cfg.base_url.startswith("http"):
        raise ValueError("--base-url musi zaczynać się od http/https")
    if not cfg.nip.isdigit() or len(cfg.nip) != 10:
        raise ValueError("NIP musi zawierać 10 cyfr")


def save_documents(
    client: KsefClient,
    docs: Iterable[Dict[str, Any]],
    out_dir: Path,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    docs_list = list(docs)
    total = len(docs_list)
    saved = 0

    for index, doc in enumerate(docs_list, start=1):
        ksef_number = (
            doc.get("ksefReferenceNumber")
            or doc.get("ksefNumber")
            or doc.get("invoiceNumber")
            or doc.get("referenceNumber")
        )
        if not ksef_number:
            LOGGER.warning("Pominięto dokument bez numeru KSeF: %s", doc)
            continue

        content = client.download_document_xml(str(ksef_number))
        filename = out_dir / f"{ksef_number}.xml"
        filename.write_bytes(content)
        saved += 1
        if progress_callback:
            progress_callback(index, total, str(filename))

    return saved
