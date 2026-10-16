"""Processing screen with a worker thread.

Playwright's sync API blocks, so we run the OrderProcessor on a QThread and
stream progress + logs back to the UI via signals. This keeps the window
responsive and lets the user stop mid-run.
"""
from __future__ import annotations

from typing import List

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QProgressBar, QTextEdit, QPushButton, QHBoxLayout,
)

from core.models import Customer
from core.order_processor import OrderProcessor, Report


class ProcessingWorker(QThread):
    progress = pyqtSignal(int, int, str)   # done, total, message
    log = pyqtSignal(str)
    finished_report = pyqtSignal(object)   # Report

    def __init__(self, config: dict, customers: List[Customer], db=None, batch_id=None):
        super().__init__()
        self.config = config
        self.orders = customers
        self.db = db
        self.batch_id = batch_id
        self._stop = False

    def request_stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        processor = OrderProcessor(
            self.config,
            db=self.db,
            batch_id=self.batch_id,
            on_progress=lambda d, t, m: self.progress.emit(d, t, m),
            on_log=lambda m: self.log.emit(m),
            should_stop=lambda: self._stop,
        )
        try:
            report = processor.process(self.orders)
        except Exception as exc:  # never crash the thread silently
            self.log.emit(f"FATAL: {exc}")
            report = Report()
        self.finished_report.emit(report)


class ProcessingScreen(QWidget):
    done = pyqtSignal(object)          # forwards the Report to the main window
    status_changed = pyqtSignal(str)  # dashboard "Processing Status" text

    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker: ProcessingWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self.current_label = QLabel("Idle.")
        self.progress = QProgressBar()
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)

        layout.addWidget(QLabel("Processing Orders"))
        layout.addWidget(self.current_label)
        layout.addWidget(self.progress)
        layout.addWidget(QLabel("Live logs:"))
        layout.addWidget(self.log_view)

        row = QHBoxLayout()
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self._on_stop)
        self.stop_btn.setEnabled(False)
        row.addStretch()
        row.addWidget(self.stop_btn)
        layout.addLayout(row)

    def start(self, config: dict, customers: List[Customer], db=None, batch_id=None) -> None:
        self.log_view.clear()
        self.progress.setValue(0)
        self.stop_btn.setEnabled(True)
        self.status_changed.emit("Processing…")

        self.worker = ProcessingWorker(config, customers, db=db, batch_id=batch_id)
        self.worker.progress.connect(self._on_progress)
        self.worker.log.connect(self._append_log)
        self.worker.finished_report.connect(self._on_finished)
        self.worker.start()

    def _on_progress(self, done: int, total: int, msg: str) -> None:
        self.current_label.setText(msg)
        self.progress.setMaximum(max(total, 1))
        self.progress.setValue(done)

    def _append_log(self, msg: str) -> None:
        self.log_view.append(msg)

    def _on_stop(self) -> None:
        if self.worker:
            self.worker.request_stop()
            self._append_log("Stop requested — finishing current order…")

    def _on_finished(self, report: Report) -> None:
        self.stop_btn.setEnabled(False)
        self.current_label.setText("Done.")
        self.status_changed.emit("Done")
        self._append_log("\n=== RUN COMPLETE ===\n" + report.as_text())
        self.done.emit(report)
