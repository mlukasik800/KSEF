# KSeF Downloader (CLI + GUI)

Ulepszona wersja programu do automatycznego pobierania dokumentów z KSeF na podstawie certyfikatu.

## Co nowego

- ✅ **Interfejs graficzny (GUI)** oparty o `tkinter`
- ✅ Tryb **CLI** nadal dostępny
- ✅ Walidacja danych wejściowych (NIP, token, URL)
- ✅ Pasek postępu i log działań w GUI

## Wymagania

- Python 3.10+
- Certyfikat klienta:
  - `PKCS12` (`.p12` / `.pfx`) lub
  - para `PEM` (`cert.pem` + `key.pem`)
- Token KSeF (Bearer)

## Instalacja

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Uruchomienie GUI

```bash
python ksef_downloader.py --gui
```

W GUI wpisujesz parametry (URL, NIP, token, daty, certyfikat), wybierasz katalog i klikasz **Pobierz dokumenty**.

## Uruchomienie CLI (przykład PKCS12)

```bash
python ksef_downloader.py \
  --base-url "https://ksef.mf.gov.pl" \
  --nip "1234567890" \
  --token "<TOKEN_KSEF>" \
  --from-date "2025-01-01" \
  --to-date "2025-01-31" \
  --cert-type pkcs12 \
  --cert-path "/sciezka/certyfikat.p12" \
  --cert-password "haslo" \
  --out-dir "./downloads"
```

## Struktura projektu

- `ksef_core.py` – logika API KSeF i zapisu dokumentów
- `ksef_gui.py` – interfejs graficzny
- `ksef_downloader.py` – punkt startowy (CLI/GUI)

## Uwagi

- Endpointy KSeF mogą różnić się między środowiskami test/prod.
- Jeśli Twoje środowisko ma inny routing, dostosuj URL-e w `ksef_core.py`.
