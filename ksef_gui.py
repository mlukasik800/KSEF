from __future__ import annotations

from pathlib import Path
from threading import Thread

from ksef_core import KsefClient, KsefConfig, parse_and_validate_dates, save_documents, validate_config


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
        raise RuntimeError(
            "Brak biblioteki PySide6. Zainstaluj requirements.txt i uruchom ponownie GUI."
        ) from exc

    class KsefMainWindow(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("KSeF Downloader Pro")
            self.resize(1000, 760)
            self._is_running = False
            self._build_ui()

        def _build_ui(self) -> None:
            central = QWidget()
            root = QVBoxLayout(central)
            root.setContentsMargins(14, 14, 14, 14)
            root.setSpacing(10)

            header = QLabel("KSeF Downloader")
            header.setStyleSheet("font-size: 24px; font-weight: 600;")
            subtitle = QLabel("Nowoczesny interfejs (Qt) do pobierania dokumentów z KSeF")
            subtitle.setStyleSheet("color: #9BA3AF;")
            root.addWidget(header)
            root.addWidget(subtitle)

            api_group = QGroupBox("Konfiguracja API")
            api_form = QFormLayout(api_group)
            self.base_url = QLineEdit("https://ksef.mf.gov.pl")
            self.nip = QLineEdit()
            self.token = QLineEdit()
            self.token.setEchoMode(QLineEdit.EchoMode.Password)
            self.from_date = QLineEdit()
            self.to_date = QLineEdit()
            self.out_dir = QLineEdit("./downloads")
            pick_out = QPushButton("Wybierz katalog")
            pick_out.clicked.connect(self.pick_out_dir)

            out_row = QWidget()
            out_l = QHBoxLayout(out_row)
            out_l.setContentsMargins(0, 0, 0, 0)
            out_l.addWidget(self.out_dir)
            out_l.addWidget(pick_out)

            api_form.addRow("Base URL", self.base_url)
            api_form.addRow("NIP", self.nip)
            api_form.addRow("Token", self.token)
            api_form.addRow("Data od (YYYY-MM-DD)", self.from_date)
            api_form.addRow("Data do (YYYY-MM-DD)", self.to_date)
            api_form.addRow("Katalog wyjściowy", out_row)
            root.addWidget(api_group)

            cert_group = QGroupBox("Uwierzytelnianie certyfikatem")
            cert_layout = QGridLayout(cert_group)

            self.cert_type = QComboBox()
            self.cert_type.addItems(["pkcs12", "pem"])
            self.cert_type.currentTextChanged.connect(self.toggle_cert_fields)

            self.cert_path = QLineEdit()
            self.cert_password = QLineEdit()
            self.cert_password.setEchoMode(QLineEdit.EchoMode.Password)
            pick_cert = QPushButton("Certyfikat .p12/.pfx")
            pick_cert.clicked.connect(self.pick_cert)

            self.cert_pem = QLineEdit()
            self.key_pem = QLineEdit()
            pick_cert_pem = QPushButton("Cert PEM")
            pick_cert_pem.clicked.connect(self.pick_cert_pem)
            pick_key_pem = QPushButton("Klucz PEM")
            pick_key_pem.clicked.connect(self.pick_key_pem)

            cert_layout.addWidget(QLabel("Typ certyfikatu"), 0, 0)
            cert_layout.addWidget(self.cert_type, 0, 1)

            self.pkcs12_box = QFrame()
            pkcs12_l = QGridLayout(self.pkcs12_box)
            pkcs12_l.setContentsMargins(0, 0, 0, 0)
            pkcs12_l.addWidget(self.cert_path, 0, 0)
            pkcs12_l.addWidget(pick_cert, 0, 1)
            pkcs12_l.addWidget(QLabel("Hasło"), 1, 0)
            pkcs12_l.addWidget(self.cert_password, 1, 1)

            self.pem_box = QFrame()
            pem_l = QGridLayout(self.pem_box)
            pem_l.setContentsMargins(0, 0, 0, 0)
            pem_l.addWidget(self.cert_pem, 0, 0)
            pem_l.addWidget(pick_cert_pem, 0, 1)
            pem_l.addWidget(self.key_pem, 1, 0)
            pem_l.addWidget(pick_key_pem, 1, 1)

            cert_layout.addWidget(self.pkcs12_box, 1, 0, 1, 2)
            cert_layout.addWidget(self.pem_box, 1, 0, 1, 2)

            options = QWidget()
            options_l = QHBoxLayout(options)
            options_l.setContentsMargins(0, 0, 0, 0)
            self.insecure = QCheckBox("Wyłącz SSL verify (insecure)")
            self.overwrite = QCheckBox("Nadpisuj istniejące pliki")
            options_l.addWidget(self.insecure)
            options_l.addWidget(self.overwrite)
            options_l.addStretch()
            cert_layout.addWidget(options, 2, 0, 1, 2)

            root.addWidget(cert_group)
            self.toggle_cert_fields(self.cert_type.currentText())

            self.download_btn = QPushButton("Pobierz dokumenty")
            self.download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.download_btn.clicked.connect(self.start_download)
            self.progress = QProgressBar()
            self.progress.setValue(0)
            self.status = QLabel("Gotowe")
            self.status.setStyleSheet("color: #9BA3AF;")

            root.addWidget(self.download_btn)
            root.addWidget(self.progress)
            root.addWidget(self.status)

            logs_group = QGroupBox("Log")
            logs_l = QVBoxLayout(logs_group)
            self.log = QPlainTextEdit()
            self.log.setReadOnly(True)
            logs_l.addWidget(self.log)
            root.addWidget(logs_group, stretch=1)

            self.setCentralWidget(central)

        def append_log(self, msg: str) -> None:
            self.log.appendPlainText(msg)

        def on_ui(self, fn, *args) -> None:
            QTimer.singleShot(0, lambda: fn(*args))

        def set_running(self, running: bool) -> None:
            self._is_running = running
            self.download_btn.setEnabled(not running)

        def toggle_cert_fields(self, cert_type: str) -> None:
            is_pkcs12 = cert_type == "pkcs12"
            self.pkcs12_box.setVisible(is_pkcs12)
            self.pem_box.setVisible(not is_pkcs12)

        def pick_out_dir(self) -> None:
            path = QFileDialog.getExistingDirectory(self, "Wybierz katalog")
            if path:
                self.out_dir.setText(path)

        def pick_cert(self) -> None:
            path, _ = QFileDialog.getOpenFileName(self, "Wybierz certyfikat", filter="PKCS12 (*.p12 *.pfx);;Wszystkie (*.*)")
            if path:
                self.cert_path.setText(path)

        def pick_cert_pem(self) -> None:
            path, _ = QFileDialog.getOpenFileName(self, "Wybierz cert PEM", filter="PEM (*.pem *.crt);;Wszystkie (*.*)")
            if path:
                self.cert_pem.setText(path)

        def pick_key_pem(self) -> None:
            path, _ = QFileDialog.getOpenFileName(self, "Wybierz klucz PEM", filter="PEM (*.pem *.key);;Wszystkie (*.*)")
            if path:
                self.key_pem.setText(path)

        def start_download(self) -> None:
            if self._is_running:
                return
            self.progress.setValue(0)
            self.set_running(True)
            Thread(target=self._download_worker, daemon=True).start()

        def _download_worker(self) -> None:
            try:
                cfg = KsefConfig(
                    base_url=self.base_url.text().strip(),
                    nip=self.nip.text().strip(),
                    token=self.token.text().strip(),
                    out_dir=Path(self.out_dir.text().strip()),
                    cert_type=self.cert_type.currentText(),
                    cert_path=Path(self.cert_path.text().strip()) if self.cert_path.text().strip() else None,
                    cert_password=self.cert_password.text(),
                    cert_pem=Path(self.cert_pem.text().strip()) if self.cert_pem.text().strip() else None,
                    key_pem=Path(self.key_pem.text().strip()) if self.key_pem.text().strip() else None,
                    verify_ssl=not self.insecure.isChecked(),
                )
                validate_config(cfg)
                parse_and_validate_dates(self.from_date.text().strip(), self.to_date.text().strip())

                self.on_ui(self.status.setText, "Łączenie z KSeF...")
                client = KsefClient(cfg)
                docs = client.list_documents(self.from_date.text().strip(), self.to_date.text().strip())
                self.on_ui(self.append_log, f"Znaleziono dokumentów: {len(docs)}")

                def progress_callback(current: int, total: int, message: str) -> None:
                    pct = int((current / total) * 100) if total else 0
                    self.on_ui(self.progress.setValue, pct)
                    self.on_ui(self.status.setText, f"Przetworzono {current}/{total}")
                    self.on_ui(self.append_log, message)

                stats = save_documents(client, docs, cfg.out_dir, progress_callback=progress_callback, overwrite=self.overwrite.isChecked())
                self.on_ui(self.status.setText, f"Gotowe. Zapisano {stats.saved}/{stats.total}")
                self.on_ui(
                    self.append_log,
                    f"Podsumowanie: zapisano={stats.saved}, pominięto={stats.skipped}, błędy={stats.failed}, razem={stats.total}",
                )
            except Exception as exc:  # noqa: BLE001
                self.on_ui(self.status.setText, "Błąd")
                self.on_ui(self.append_log, f"BŁĄD: {exc}")
                self.on_ui(QMessageBox.critical, self, "Błąd", str(exc))
            finally:
                self.on_ui(self.set_running, False)

    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(24, 26, 32))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.Base, QColor(30, 33, 40))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(38, 42, 52))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.Text, QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.Button, QColor(45, 49, 61))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 77, 79))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(59, 130, 246))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    app.setPalette(palette)

    app.setStyleSheet(
        """
        QGroupBox { font-weight: 600; border: 1px solid #3b4252; border-radius: 8px; margin-top: 12px; padding: 10px; }
        QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        QPushButton { background-color: #2563eb; border: none; border-radius: 6px; padding: 8px 12px; font-weight: 600; }
        QPushButton:hover { background-color: #1d4ed8; }
        QPushButton:disabled { background-color: #4b5563; }
        QLineEdit, QComboBox, QPlainTextEdit { border: 1px solid #4b5563; border-radius: 6px; padding: 6px; }
        """
    )

    window = KsefMainWindow()
    window.show()
    app.exec()
