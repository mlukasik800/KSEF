from __future__ import annotations

import json
import logging
import re
import time
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

try:
    from requests_pkcs12 import Pkcs12Adapter  # type: ignore
except Exception:  # pragma: no cover
    Pkcs12Adapter = None

LOGGER = logging.getLogger("ksef-downloader")
BOOKKEEPING_SYSTEMS = ("mala_ksiegowosc_rp", "symfonia", "inne")


@dataclass
class ClientProfile:
    name: str
    nip: str
    bookkeeping_system: str = "inne"


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


@dataclass
class DownloadStats:
    total: int = 0
    saved: int = 0
    skipped: int = 0
    failed: int = 0
    saved_files: List[Path] = field(default_factory=list)


class KsefClient:
    def __init__(self, cfg: KsefConfig, timeout: int = 60, retries: int = 2, retry_delay: float = 1.0) -> None:
        self.cfg = cfg
        self.timeout = timeout
        self.retries = retries
        self.retry_delay = retry_delay
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

    def _request_with_retry(self, method: str, url: str, **kwargs: Any):
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.retries + 2):
            try:
                response = self.session.request(method, url, timeout=self.timeout, **kwargs)
                response.raise_for_status()
                return response
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                LOGGER.warning("Błąd żądania %s %s (próba %s): %s", method, url, attempt, exc)
                if attempt <= self.retries:
                    time.sleep(self.retry_delay)

        if last_exc:
            raise last_exc
        raise RuntimeError("Nieznany błąd HTTP")

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
            response = self._request_with_retry("POST", url, data=json.dumps(payload))
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
        response = self._request_with_retry("GET", url)

        ctype = response.headers.get("Content-Type", "")
        if "application/json" in ctype.lower():
            payload = response.json()
            raw = payload.get("invoice") or payload.get("xml") or ""
            return raw.encode("utf-8")

        return response.content


def parse_and_validate_dates(from_date: str, to_date: str) -> None:
    fmt = "%Y-%m-%d"
    try:
        start = datetime.strptime(from_date, fmt)
        end = datetime.strptime(to_date, fmt)
    except ValueError as exc:
        raise ValueError("Daty muszą mieć format YYYY-MM-DD") from exc

    if start > end:
        raise ValueError("Data 'od' nie może być późniejsza niż data 'do'")


def validate_profile(profile: ClientProfile) -> None:
    if not profile.name.strip():
        raise ValueError("Nazwa klienta nie może być pusta")
    if not profile.nip.isdigit() or len(profile.nip) != 10:
        raise ValueError("NIP klienta musi zawierać 10 cyfr")
    if profile.bookkeeping_system not in BOOKKEEPING_SYSTEMS:
        raise ValueError("System księgowy musi być: mala_ksiegowosc_rp, symfonia, inne")


def validate_config(cfg: KsefConfig) -> None:
    if not cfg.token:
        raise ValueError("Brak tokenu KSeF.")
    if not cfg.base_url.startswith("http"):
        raise ValueError("--base-url musi zaczynać się od http/https")
    if not cfg.nip.isdigit() or len(cfg.nip) != 10:
        raise ValueError("NIP musi zawierać 10 cyfr")


def extract_ksef_number(doc: Dict[str, Any]) -> Optional[str]:
    for key in ("ksefReferenceNumber", "ksefNumber", "invoiceNumber", "referenceNumber"):
        if doc.get(key):
            return str(doc[key])
    return None


def safe_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)


def client_output_dir(base_out_dir: Path, profile: ClientProfile) -> Path:
    return base_out_dir / f"{safe_filename(profile.name)}_{profile.nip}"


def load_profiles(path: Path) -> List[ClientProfile]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    profiles = [ClientProfile(**item) for item in raw]
    for p in profiles:
        validate_profile(p)
    return profiles


def save_profiles(path: Path, profiles: List[ClientProfile]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(p) for p in profiles], ensure_ascii=False, indent=2), encoding="utf-8")


def upsert_profile(path: Path, profile: ClientProfile) -> List[ClientProfile]:
    validate_profile(profile)
    profiles = [p for p in load_profiles(path) if p.nip != profile.nip]
    profiles.append(profile)
    profiles.sort(key=lambda p: p.name.lower())
    save_profiles(path, profiles)
    return profiles


def delete_profile(path: Path, nip: str) -> List[ClientProfile]:
    profiles = [p for p in load_profiles(path) if p.nip != nip]
    save_profiles(path, profiles)
    return profiles




def write_download_manifest(out_dir: Path, profile: ClientProfile, stats: DownloadStats) -> Path:
    manifest = {
        "client": asdict(profile),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "stats": {
            "total": stats.total,
            "saved": stats.saved,
            "skipped": stats.skipped,
            "failed": stats.failed,
        },
        "files": [str(p.name) for p in stats.saved_files],
    }
    path = out_dir / "manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def create_zip_from_dir(source_dir: Path, zip_path: Path) -> Path:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file in sorted(source_dir.glob("*.xml")):
            zf.write(file, arcname=file.name)
        manifest = source_dir / "manifest.json"
        if manifest.exists():
            zf.write(manifest, arcname=manifest.name)
    return zip_path

def save_documents(
    client: KsefClient,
    docs: Iterable[Dict[str, Any]],
    out_dir: Path,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    overwrite: bool = False,
) -> DownloadStats:
    out_dir.mkdir(parents=True, exist_ok=True)
    docs_list = list(docs)
    stats = DownloadStats(total=len(docs_list))
    seen: set[str] = set()

    for index, doc in enumerate(docs_list, start=1):
        ksef_number = extract_ksef_number(doc)
        if not ksef_number:
            stats.failed += 1
            continue
        if ksef_number in seen:
            stats.skipped += 1
            continue
        seen.add(ksef_number)

        filename = out_dir / f"{safe_filename(ksef_number)}.xml"
        if filename.exists() and not overwrite:
            stats.skipped += 1
            if progress_callback:
                progress_callback(index, stats.total, f"Pominięto istniejący plik: {filename}")
            continue

        try:
            filename.write_bytes(client.download_document_xml(ksef_number))
            stats.saved += 1
            stats.saved_files.append(filename)
            if progress_callback:
                progress_callback(index, stats.total, f"Zapisano: {filename}")
        except Exception as exc:  # noqa: BLE001
            stats.failed += 1
            if progress_callback:
                progress_callback(index, stats.total, f"Błąd {ksef_number}: {exc}")

    return stats
