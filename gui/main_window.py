"""Main application window — dashboard + all screens via a QStackedWidget.

Workflow:  Upload PDF -> Parse -> Review -> Process -> Report
Dashboard shows live counts: orders, processing status, success, failure.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QStackedWidget, QFileDialog, QMessageBox, QLabel, QFrame, QGridLayout,
)

from core.pdf_reader import PDFReader
from core.order_parser import OrderParser
from core.database import Database
from core.models import Customer

from .review_screen import ReviewScreen
from .processing_screen import ProcessingScreen
from .report_screen import ReportScreen

logger = logging.getLogger(__name__)


def load_config() -> dict:
    for name in ("config.json", "config.example.json"):
        p = Path(name)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    raise FileNotFoundError("No config.json or config.example.json found.")


class StatCard(QFrame):
    """A small dashboard tile showing a label and a big value."""

    def __init__(self, title: str):
        super().__init__()
        self.setFrameShape(QFrame.Shape.StyledPanel)
        lay = QVBoxLayout(self)
        self.title = QLabel(title)
        self.value = QLabel("0")
        f = self.value.font()
        f.setPointSize(22)
        f.setBold(True)
        self.value.setFont(f)
        lay.addWidget(self.title)
        lay.addWidget(self.value)

    def set(self, value) -> None:
        self.value.setText(str(value))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Order Automation Assistant")
        self.resize(1150, 760)

        self.config = load_config()
        self.db = Database()
        pdf_cfg = self.config.get("pdf", {})
        self.pdf_reader = PDFReader(
            use_ocr=pdf_cfg.get("use_ocr", False),
            ocr_lang=pdf_cfg.get("ocr_lang", "ben+eng"),
        )
        br = self.config["business_rules"]
        self.parser = OrderParser(
            price_per_piece=br["price_per_piece"],
            default_payment=br.get("default_payment", "COD"),
            messenger_marker=br.get("messenger_marker", "(messenger)"),
            bill_note_template=br.get("bill_note_template", "({amount} takar bill hobe)"),
        )

        self.customers: List[Customer] = []
        self.pdf_path: str | None = None
        self.batch_id: int | None = None

        self._build_ui()

    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)

        # ---- Dashboard cards ----
        dash = QGridLayout()
        self.card_orders = StatCard("Customers / Orders")
        self.card_status = StatCard("Processing Status")
        self.card_success = StatCard("Success")
        self.card_failed = StatCard("Failure")
        self.card_status.value.setText("Idle")
        f = self.card_status.value.font(); f.setPointSize(14); self.card_status.value.setFont(f)
        dash.addWidget(self.card_orders, 0, 0)
        dash.addWidget(self.card_status, 0, 1)
        dash.addWidget(self.card_success, 0, 2)
        dash.addWidget(self.card_failed, 0, 3)
        root.addLayout(dash)

        # ---- Action bar ----
        nav = QHBoxLayout()
        self.upload_btn = QPushButton("1. Upload PDF")
        self.parse_btn = QPushButton("2. Parse Orders")
        self.review_btn = QPushButton("3. Review Orders")
        self.process_btn = QPushButton("4. Process Orders")
        self.report_btn = QPushButton("5. View Report")
        for b in (self.upload_btn, self.parse_btn, self.review_btn,
                  self.process_btn, self.report_btn):
            nav.addWidget(b)
        root.addLayout(nav)

        self.status_label = QLabel("Upload a PDF to begin.")
        root.addWidget(self.status_label)

        # ---- Screens ----
        self.stack = QStackedWidget()
        self.review_screen = ReviewScreen()
        self.processing_screen = ProcessingScreen()
        self.report_screen = ReportScreen()

        welcome = QLabel("AI Order Automation Assistant\n\n"
                         "Read PDFs → review customers & items → auto-create orders on "
                         "editionbreezy.com (cart-based checkout).")
        welcome.setContentsMargins(20, 20, 20, 20)

        self.stack.addWidget(welcome)                  # 0
        self.stack.addWidget(self.review_screen)       # 1
        self.stack.addWidget(self.processing_screen)   # 2
        self.stack.addWidget(self.report_screen)       # 3
        root.addWidget(self.stack)

        self.setCentralWidget(central)

        self.upload_btn.clicked.connect(self.on_upload)
        self.parse_btn.clicked.connect(self.on_parse)
        self.review_btn.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        self.process_btn.clicked.connect(self.on_process)
        self.report_btn.clicked.connect(lambda: self.stack.setCurrentIndex(3))
        self.processing_screen.done.connect(self.on_processing_done)
        self.processing_screen.status_changed.connect(self.card_status.value.setText)

    # ------------------------------------------------------------------ #
    def on_upload(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select order PDF", "", "PDF Files (*.pdf)")
        if not path:
            return
        self.pdf_path = path
        self.status_label.setText(f"Loaded PDF: {Path(path).name}")
        self.card_status.value.setText("PDF loaded")

    def on_parse(self) -> None:
        if not self.pdf_path:
            QMessageBox.warning(self, "No PDF", "Please upload a PDF first.")
            return
        try:
            text = self.pdf_reader.extract_text(self.pdf_path)
            self.customers = self.parser.parse(text)
        except Exception as exc:
            QMessageBox.critical(self, "Parse error", str(exc))
            logger.exception("Parsing failed")
            return

        if not self.customers:
            QMessageBox.information(self, "No orders", "No customers detected in the PDF.")
            return

        self.batch_id = self.db.create_batch(self.pdf_path)
        self.db.save_customers(self.batch_id, self.customers)

        self.review_screen.load_customers(self.customers)
        self.stack.setCurrentIndex(1)
        total_items = sum(len(c.items) for c in self.customers)
        self.card_orders.set(f"{len(self.customers)} / {total_items} items")
        self.card_status.value.setText("Ready to review")
        self.status_label.setText(
            f"Parsed {len(self.customers)} customer(s), {total_items} item(s). Review and confirm.")

    def on_process(self) -> None:
        self.review_screen.save_changes()
        confirmed = [c for c in self.customers if c.status == "Confirmed"]
        if not confirmed:
            QMessageBox.warning(self, "Nothing confirmed",
                                "Confirm at least one customer in the Review screen first.")
            return
        self.stack.setCurrentIndex(2)
        self.card_status.value.setText("Processing…")
        self.status_label.setText(f"Processing {len(confirmed)} confirmed customer(s)…")
        self.processing_screen.start(self.config, self.customers, db=self.db, batch_id=self.batch_id)

    def on_processing_done(self, report) -> None:
        self.report_screen.show_report(report)
        self.card_success.set(report.success)
        self.card_failed.set(report.failed)
        self.card_status.value.setText("Done")
        self.status_label.setText(f"Done. Success: {report.success}, Failed: {report.failed}.")
        self.stack.setCurrentIndex(3)

    def closeEvent(self, event) -> None:  # noqa: N802
        self.db.close()
        super().closeEvent(event)
