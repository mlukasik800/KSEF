from __future__ import annotations

from pathlib import Path
from threading import Thread

from ksef_core import (
    BOOKKEEPING_SYSTEMS,
    ClientProfile,
    KsefClient,
    KsefConfig,
    client_output_dir,
    create_zip_from_dir,
    delete_profile,
    load_profiles,
    parse_and_validate_dates,
    save_documents,
    upsert_profile,
    write_download_manifest,
    validate_config,
    validate_profile,
)


def run_gui() -> None:
    try:
        from PySide6.QtCore import Qt, QTimer
        from PySide6.QtGui import QColor, QPalette
        from PySide6.QtWidgets import (
            QApplication,
            QCheckBox,
            QComboBox,
            QFileDialog,
            QFormLayout,
            QFrame,
            QGridLayout,
            QGroupBox,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QMainWindow,
            QMessageBox,
            QPlainTextEdit,
            QProgressBar,
            QPushButton,
            QVBoxLayout,
            QWidget,
        )
    except ModuleNotFoundError as exc:
        raise RuntimeError("Brak biblioteki PySide6. Zainstaluj requirements.txt i uruchom ponownie GUI.") from exc

    class Win(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("KSeF Downloader - pobieranie i zarządzanie klientami")
            self.resize(1080, 820)
            self.profiles_path = Path("./clients.json")
            self.running = False
            self._build()
            self.refresh_profiles()

        def _build(self) -> None:
            c = QWidget()
            root = QVBoxLayout(c)

            root.addWidget(QLabel("KSeF Downloader (bez księgowania - tylko pobieranie i zarządzanie)"))

            cg = QGroupBox("Klient")
            cf = QFormLayout(cg)
            self.profile = QComboBox(); self.profile.currentTextChanged.connect(self.apply_profile)
            self.client_name = QLineEdit()
            self.client_nip = QLineEdit()
            self.book = QComboBox(); self.book.addItems(list(BOOKKEEPING_SYSTEMS))

            btns = QWidget(); bl = QHBoxLayout(btns); bl.setContentsMargins(0,0,0,0)
            bsave = QPushButton("Zapisz profil"); bsave.clicked.connect(self.save_profile)
            bdel = QPushButton("Usuń profil"); bdel.clicked.connect(self.remove_profile)
            bref = QPushButton("Odśwież"); bref.clicked.connect(self.refresh_profiles)
            bl.addWidget(bsave); bl.addWidget(bdel); bl.addWidget(bref); bl.addStretch()

            cf.addRow("Profil", self.profile)
            cf.addRow("Nazwa klienta", self.client_name)
            cf.addRow("NIP", self.client_nip)
            cf.addRow("System docelowy", self.book)
            cf.addRow("", btns)
            root.addWidget(cg)

            ag = QGroupBox("Pobieranie")
            af = QFormLayout(ag)
            self.base_url = QLineEdit("https://ksef.mf.gov.pl")
            self.token = QLineEdit(); self.token.setEchoMode(QLineEdit.EchoMode.Password)
            self.from_date = QLineEdit(); self.to_date = QLineEdit()
            self.out_dir = QLineEdit("./downloads")
            outw = QWidget(); ol = QHBoxLayout(outw); ol.setContentsMargins(0,0,0,0)
            ob = QPushButton("Wybierz"); ob.clicked.connect(self.pick_out)
            ol.addWidget(self.out_dir); ol.addWidget(ob)
            af.addRow("Base URL", self.base_url)
            af.addRow("Token", self.token)
            af.addRow("Data od", self.from_date)
            af.addRow("Data do", self.to_date)
            af.addRow("Katalog bazowy", outw)
            root.addWidget(ag)

            sg = QGroupBox("Certyfikat")
            sl = QGridLayout(sg)
            self.ctype = QComboBox(); self.ctype.addItems(["pkcs12", "pem"]); self.ctype.currentTextChanged.connect(self.toggle_cert)
            self.cpath = QLineEdit(); self.cpass = QLineEdit(); self.cpass.setEchoMode(QLineEdit.EchoMode.Password)
            self.cpem = QLineEdit(); self.kpem = QLineEdit()
            sl.addWidget(QLabel("Typ"),0,0); sl.addWidget(self.ctype,0,1)

            self.pk = QFrame(); pkl = QGridLayout(self.pk); pkl.setContentsMargins(0,0,0,0)
            b1 = QPushButton(".p12/.pfx"); b1.clicked.connect(self.pick_cert)
            pkl.addWidget(self.cpath,0,0); pkl.addWidget(b1,0,1); pkl.addWidget(QLabel("Hasło"),1,0); pkl.addWidget(self.cpass,1,1)

            self.pm = QFrame(); pml = QGridLayout(self.pm); pml.setContentsMargins(0,0,0,0)
            b2 = QPushButton("Cert PEM"); b2.clicked.connect(self.pick_cpem)
            b3 = QPushButton("Klucz PEM"); b3.clicked.connect(self.pick_kpem)
            pml.addWidget(self.cpem,0,0); pml.addWidget(b2,0,1); pml.addWidget(self.kpem,1,0); pml.addWidget(b3,1,1)

            sl.addWidget(self.pk,1,0,1,2); sl.addWidget(self.pm,1,0,1,2)
            self.insecure = QCheckBox("insecure SSL")
            self.overwrite = QCheckBox("nadpisuj pliki")
            self.make_zip = QCheckBox("twórz ZIP dla klienta")
            ow = QWidget(); owl = QHBoxLayout(ow); owl.setContentsMargins(0,0,0,0); owl.addWidget(self.insecure); owl.addWidget(self.overwrite); owl.addWidget(self.make_zip); owl.addStretch()
            sl.addWidget(ow,2,0,1,2)
            self.toggle_cert(self.ctype.currentText())
            root.addWidget(sg)

            self.download = QPushButton("Pobierz dokumenty klienta")
            self.download.clicked.connect(self.start_download)
            self.progress = QProgressBar(); self.status = QLabel("Gotowe")
            self.logs = QPlainTextEdit(); self.logs.setReadOnly(True)
            root.addWidget(self.download); root.addWidget(self.progress); root.addWidget(self.status); root.addWidget(self.logs, stretch=1)

            self.setCentralWidget(c)

        def on_ui(self, fn, *args):
            QTimer.singleShot(0, lambda: fn(*args))

        def log(self, msg: str):
            self.logs.appendPlainText(msg)

        def profile_text(self, p: ClientProfile) -> str:
            return f"{p.name} | {p.nip} | {p.bookkeeping_system}"

        def refresh_profiles(self):
            self.profile.blockSignals(True)
            self.profile.clear(); self.profile.addItem("-- nowy klient --")
            for p in load_profiles(self.profiles_path):
                self.profile.addItem(self.profile_text(p))
            self.profile.blockSignals(False)

        def apply_profile(self, text: str):
            if text.startswith("--"):
                return
            try:
                name, nip, book = [x.strip() for x in text.split("|")]
            except ValueError:
                return
            self.client_name.setText(name); self.client_nip.setText(nip); self.book.setCurrentText(book)

        def get_profile(self) -> ClientProfile:
            p = ClientProfile(self.client_name.text().strip(), self.client_nip.text().strip(), self.book.currentText())
            validate_profile(p)
            return p

        def save_profile(self):
            try:
                p = self.get_profile(); upsert_profile(self.profiles_path, p); self.refresh_profiles(); self.log(f"Zapisano profil: {p.name}")
            except Exception as exc:  # noqa: BLE001
                QMessageBox.critical(self, "Błąd", str(exc))

        def remove_profile(self):
            nip = self.client_nip.text().strip()
            if not nip:
                QMessageBox.critical(self, "Błąd", "Najpierw wybierz profil lub wpisz NIP")
                return
            delete_profile(self.profiles_path, nip)
            self.refresh_profiles()
            self.log(f"Usunięto profil NIP={nip}")

        def pick_out(self):
            p = QFileDialog.getExistingDirectory(self, "Katalog")
            if p: self.out_dir.setText(p)

        def pick_cert(self):
            p, _ = QFileDialog.getOpenFileName(self, "Certyfikat", filter="PKCS12 (*.p12 *.pfx);;Wszystkie (*.*)")
            if p: self.cpath.setText(p)

        def pick_cpem(self):
            p, _ = QFileDialog.getOpenFileName(self, "Cert PEM", filter="PEM (*.pem *.crt);;Wszystkie (*.*)")
            if p: self.cpem.setText(p)

        def pick_kpem(self):
            p, _ = QFileDialog.getOpenFileName(self, "Klucz PEM", filter="PEM (*.pem *.key);;Wszystkie (*.*)")
            if p: self.kpem.setText(p)

        def toggle_cert(self, t: str):
            self.pk.setVisible(t == "pkcs12")
            self.pm.setVisible(t == "pem")

        def start_download(self):
            if self.running:
                return
            self.running = True
            self.download.setEnabled(False)
            self.progress.setValue(0)
            Thread(target=self._worker, daemon=True).start()

        def _worker(self):
            try:
                profile = self.get_profile()
                out = client_output_dir(Path(self.out_dir.text().strip()), profile)
                cfg = KsefConfig(
                    base_url=self.base_url.text().strip(),
                    nip=profile.nip,
                    token=self.token.text().strip(),
                    out_dir=out,
                    cert_type=self.ctype.currentText(),
                    cert_path=Path(self.cpath.text().strip()) if self.cpath.text().strip() else None,
                    cert_password=self.cpass.text(),
                    cert_pem=Path(self.cpem.text().strip()) if self.cpem.text().strip() else None,
                    key_pem=Path(self.kpem.text().strip()) if self.kpem.text().strip() else None,
                    verify_ssl=not self.insecure.isChecked(),
                )
                validate_config(cfg)
                parse_and_validate_dates(self.from_date.text().strip(), self.to_date.text().strip())

                client = KsefClient(cfg)
                docs = client.list_documents(self.from_date.text().strip(), self.to_date.text().strip())
                self.on_ui(self.log, f"[{profile.name}] znaleziono: {len(docs)}")

                def on_progress(c: int, t: int, msg: str):
                    self.on_ui(self.progress.setValue, int((c/t)*100) if t else 0)
                    self.on_ui(self.status.setText, f"[{profile.name}] {c}/{t}")
                    self.on_ui(self.log, msg)

                stats = save_documents(client, docs, cfg.out_dir, progress_callback=on_progress, overwrite=self.overwrite.isChecked())
                manifest = write_download_manifest(cfg.out_dir, profile, stats)
                self.on_ui(self.log, f"Zapisano manifest: {manifest}")
                if self.make_zip.isChecked():
                    zip_path = cfg.out_dir.parent / f"{cfg.out_dir.name}.zip"
                    create_zip_from_dir(cfg.out_dir, zip_path)
                    self.on_ui(self.log, f"Utworzono ZIP: {zip_path}")
                self.on_ui(self.status.setText, f"Gotowe [{profile.name}] {stats.saved}/{stats.total}")
            except Exception as exc:  # noqa: BLE001
                self.on_ui(self.status.setText, "Błąd")
                self.on_ui(self.log, f"BŁĄD: {exc}")
                self.on_ui(QMessageBox.critical, self, "Błąd", str(exc))
            finally:
                self.on_ui(self.download.setEnabled, True)
                self.running = False

    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor(24, 26, 32))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(240, 240, 240))
    pal.setColor(QPalette.ColorRole.Base, QColor(30, 33, 40))
    pal.setColor(QPalette.ColorRole.Text, QColor(240, 240, 240))
    pal.setColor(QPalette.ColorRole.Button, QColor(45, 49, 61))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(240, 240, 240))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(59, 130, 246))
    app.setPalette(pal)

    w = Win(); w.show(); app.exec()
