# KSeF Downloader (CLI + GUI)

Program do **pobierania i zarządzania dokumentami KSeF** dla biura rachunkowego.  
Nie służy do księgowania (to robisz w Małej Księgowości Rzeczpospolitej lub Symfonii).

## Co ulepszone

- Profile klientów (nazwa, NIP, system docelowy: `mala_ksiegowosc_rp` / `symfonia` / `inne`).
- Zarządzanie profilami: dodaj/edytuj/usuń.
- Pobieranie dokumentów do osobnych katalogów per klient.
- GUI w PySide6 + CLI dla automatyzacji.
- Retry i walidacja wejścia.
- Manifest `manifest.json` po każdym pobraniu + opcjonalna paczka ZIP do przekazania/importu.

## Instalacja

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## GUI

```bash
python ksef_downloader.py --gui
```

## CLI (przykład)

```bash
python ksef_downloader.py \
  --base-url "https://ksef.mf.gov.pl" \
  --token "<TOKEN_KSEF>" \
  --from-date "2025-01-01" \
  --to-date "2025-01-31" \
  --client-name "Klient A" \
  --client-nip "1234567890" \
  --bookkeeping-system "symfonia" \
  --save-client \
  --profiles-path "./clients.json" \
  --cert-type pkcs12 \
  --cert-path "/sciezka/certyfikat.p12" \
  --cert-password "haslo" \
  --out-dir "./downloads" \
  --zip-output
```

## Ważne

- Program tylko pobiera i organizuje dokumenty XML z KSeF.
- Księgowanie wykonujesz dalej w swoim systemie.
