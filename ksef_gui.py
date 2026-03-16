from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from ksef_core import KsefClient, KsefConfig, save_documents, validate_config


class KsefDownloaderGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("KSeF Downloader")
        self.root.geometry("760x560")

        self.base_url = tk.StringVar(value="https://ksef.mf.gov.pl")
        self.nip = tk.StringVar()
        self.token = tk.StringVar()
        self.from_date = tk.StringVar()
        self.to_date = tk.StringVar()
        self.out_dir = tk.StringVar(value="./downloads")
        self.cert_type = tk.StringVar(value="pkcs12")
        self.cert_path = tk.StringVar()
        self.cert_password = tk.StringVar()
        self.cert_pem = tk.StringVar()
        self.key_pem = tk.StringVar()
        self.insecure = tk.BooleanVar(value=False)

        self.status = tk.StringVar(value="Gotowe")
        self.progress = tk.IntVar(value=0)

        self._build()

    def _build(self) -> None:
        frm = ttk.Frame(self.root, padding=12)
        frm.pack(fill="both", expand=True)

        fields = [
            ("Base URL", self.base_url),
            ("NIP", self.nip),
            ("Token", self.token),
            ("Data od (YYYY-MM-DD)", self.from_date),
            ("Data do (YYYY-MM-DD)", self.to_date),
            ("Katalog wyjściowy", self.out_dir),
        ]

        for i, (label, var) in enumerate(fields):
            ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w", pady=4)
            ttk.Entry(frm, textvariable=var, width=70, show="*" if label == "Token" else "").grid(
                row=i, column=1, sticky="ew", padx=8
            )

        ttk.Button(frm, text="Wybierz katalog", command=self.pick_out_dir).grid(row=5, column=2)

        ttk.Label(frm, text="Typ certyfikatu").grid(row=6, column=0, sticky="w", pady=4)
        cert_combo = ttk.Combobox(frm, textvariable=self.cert_type, values=["pkcs12", "pem"], state="readonly")
        cert_combo.grid(row=6, column=1, sticky="w", padx=8)
        cert_combo.bind("<<ComboboxSelected>>", lambda _: self._toggle_cert_fields())

        self.pkcs12_frame = ttk.Frame(frm)
        self.pkcs12_frame.grid(row=7, column=1, sticky="ew", padx=8)
        ttk.Entry(self.pkcs12_frame, textvariable=self.cert_path, width=52).grid(row=0, column=0, padx=(0, 4))
        ttk.Button(self.pkcs12_frame, text="Certyfikat .p12/.pfx", command=self.pick_cert).grid(row=0, column=1)
        ttk.Entry(self.pkcs12_frame, textvariable=self.cert_password, width=20, show="*").grid(row=0, column=2, padx=(8, 0))

        self.pem_frame = ttk.Frame(frm)
        self.pem_frame.grid(row=8, column=1, sticky="ew", padx=8)
        ttk.Entry(self.pem_frame, textvariable=self.cert_pem, width=36).grid(row=0, column=0, padx=(0, 4))
        ttk.Button(self.pem_frame, text="Cert PEM", command=self.pick_cert_pem).grid(row=0, column=1)
        ttk.Entry(self.pem_frame, textvariable=self.key_pem, width=36).grid(row=1, column=0, padx=(0, 4), pady=(4, 0))
        ttk.Button(self.pem_frame, text="Klucz PEM", command=self.pick_key_pem).grid(row=1, column=1, pady=(4, 0))

        ttk.Checkbutton(frm, text="Wyłącz weryfikację SSL (insecure)", variable=self.insecure).grid(
            row=9, column=1, sticky="w", padx=8, pady=6
        )

        btn_frame = ttk.Frame(frm)
        btn_frame.grid(row=10, column=1, sticky="w", padx=8, pady=(8, 8))
        ttk.Button(btn_frame, text="Pobierz dokumenty", command=self.start_download).pack(side="left")

        ttk.Progressbar(frm, variable=self.progress, maximum=100).grid(row=11, column=1, sticky="ew", padx=8)
        ttk.Label(frm, textvariable=self.status).grid(row=12, column=1, sticky="w", padx=8, pady=(4, 8))

        self.log_text = tk.Text(frm, height=12, width=92)
        self.log_text.grid(row=13, column=0, columnspan=3, sticky="nsew")

        frm.columnconfigure(1, weight=1)
        frm.rowconfigure(13, weight=1)
        self._toggle_cert_fields()

    def _toggle_cert_fields(self) -> None:
        if self.cert_type.get() == "pkcs12":
            self.pkcs12_frame.tkraise()
        else:
            self.pem_frame.tkraise()

    def pick_out_dir(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.out_dir.set(path)

    def pick_cert(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("PKCS12", "*.p12 *.pfx"), ("Wszystkie", "*.*")])
        if path:
            self.cert_path.set(path)

    def pick_cert_pem(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("PEM", "*.pem *.crt"), ("Wszystkie", "*.*")])
        if path:
            self.cert_pem.set(path)

    def pick_key_pem(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("PEM", "*.pem *.key"), ("Wszystkie", "*.*")])
        if path:
            self.key_pem.set(path)

    def log(self, msg: str) -> None:
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")

    def start_download(self) -> None:
        thread = threading.Thread(target=self._download, daemon=True)
        thread.start()

    def _download(self) -> None:
        try:
            cfg = KsefConfig(
                base_url=self.base_url.get().strip(),
                nip=self.nip.get().strip(),
                token=self.token.get().strip(),
                out_dir=Path(self.out_dir.get().strip()),
                cert_type=self.cert_type.get().strip(),
                cert_path=Path(self.cert_path.get().strip()) if self.cert_path.get().strip() else None,
                cert_password=self.cert_password.get(),
                cert_pem=Path(self.cert_pem.get().strip()) if self.cert_pem.get().strip() else None,
                key_pem=Path(self.key_pem.get().strip()) if self.key_pem.get().strip() else None,
                verify_ssl=not self.insecure.get(),
            )
            validate_config(cfg)
            self.status.set("Łączenie z KSeF...")
            client = KsefClient(cfg)
            docs = client.list_documents(self.from_date.get().strip(), self.to_date.get().strip())
            self.log(f"Znaleziono dokumentów: {len(docs)}")

            def on_progress(current: int, total: int, filename: str) -> None:
                pct = int((current / total) * 100) if total else 0
                self.progress.set(pct)
                self.status.set(f"Pobrano {current}/{total}")
                self.log(f"Zapisano: {filename}")

            saved = save_documents(client, docs, cfg.out_dir, progress_callback=on_progress)
            self.status.set(f"Gotowe. Pobrano {saved} dokumentów.")
            self.log(f"Sukces: zapisano {saved} dokumentów")
        except Exception as exc:  # noqa: BLE001
            self.status.set("Błąd")
            self.log(f"BŁĄD: {exc}")
            messagebox.showerror("Błąd", str(exc))


def run_gui() -> None:
    root = tk.Tk()
    root.style = ttk.Style()  # type: ignore[attr-defined]
    if "clam" in root.style.theme_names():
        root.style.theme_use("clam")
    KsefDownloaderGUI(root)
    root.mainloop()
