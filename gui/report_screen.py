"""Report screen: summary of the last run + export to file."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTextEdit, QPushButton, QHBoxLayout, QFileDialog, QMessageBox,
)

from core.order_processor import Report


class ReportScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.report: Report | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Final Report"))
        self.summary = QTextEdit()
        self.summary.setReadOnly(True)
        layout.addWidget(self.summary)

        row = QHBoxLayout()
        self.export_txt = QPushButton("Export as TXT")
        self.export_csv = QPushButton("Export failures as CSV")
        self.export_txt.clicked.connect(self._export_txt)
        self.export_csv.clicked.connect(self._export_csv)
        row.addWidget(self.export_txt)
        row.addWidget(self.export_csv)
        layout.addLayout(row)

    def show_report(self, report: Report) -> None:
        self.report = report
        self.summary.setPlainText(report.as_text())

    def _export_txt(self) -> None:
        if not self.report:
            return
        default = f"reports/report_{datetime.now():%Y%m%d_%H%M%S}.txt"
        Path("reports").mkdir(exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(self, "Export report", default, "Text (*.txt)")
        if path:
            Path(path).write_text(self.report.as_text(), encoding="utf-8")
            QMessageBox.information(self, "Exported", f"Saved to {path}")

    def _export_csv(self) -> None:
        if not self.report or not self.report.failures:
            QMessageBox.information(self, "Nothing to export", "No failures to export.")
            return
        default = f"reports/failures_{datetime.now():%Y%m%d_%H%M%S}.csv"
        Path("reports").mkdir(exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(self, "Export failures", default, "CSV (*.csv)")
        if path:
            pd.DataFrame(self.report.failures, columns=["Order", "Reason"]).to_csv(path, index=False)
            QMessageBox.information(self, "Exported", f"Saved to {path}")
