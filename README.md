# KSeF Downloader (CLI + GUI)

Ulepszony program do automatycznego pobierania dokumentów z KSeF na podstawie certyfikatu klienta.

## Najważniejsze ulepszenia

- ✅ GUI przeniesione z `tkinter` na **PySide6 (Qt)** – nowoczesny, dużo ładniejszy interfejs.
- ✅ Bezpieczniejsze działanie: walidacja NIP, URL i zakresu dat.
- ✅ Lepsza odporność na chwilowe problemy sieciowe (retry żądań HTTP).
- ✅ Czytelne podsumowanie pobierania: zapisane / pominięte / błędy.
- ✅ Obsługa pomijania istniejących plików lub ich nadpisywania.

## Wymagania

- Python 3.10+
- certyfikat klienta:
  - `PKCS12` (`.p12` / `.pfx`) lub
  - para `PEM` (`cert.pem` + `key.pem`)
- token KSeF (Bearer)

## Instalacja

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Uruchomienie GUI (PySide6/Qt)

```bash
python ksef_downloader.py --gui
```

W GUI wpisujesz parametry, wybierasz certyfikat i katalog, a potem klikasz **Pobierz dokumenty**.

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
  --out-dir "./downloads" \
  --page-size 100
```

## Przydatne opcje CLI

- `--overwrite` – nadpisuj istniejące pliki XML.
- `--insecure` – wyłącza weryfikację SSL (niezalecane).
- `--debug` – szczegółowe logowanie.

## Struktura projektu

- `ksef_core.py` – logika API KSeF, walidacja, retry, zapis dokumentów.
- `ksef_gui.py` – nowoczesny interfejs PySide6 (Qt).
- `ksef_downloader.py` – punkt startowy (CLI/GUI).
- `tests/test_core.py` – testy funkcji pomocniczych.

## Uwagi

- Endpointy KSeF mogą różnić się między środowiskami test/prod.
- W razie innego routingu dostosuj URL-e w `ksef_core.py`.
