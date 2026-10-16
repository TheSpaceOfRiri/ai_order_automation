"""Batch order processor.

Orchestrates validation + cart-based browser automation across many customers,
continuing past individual failures and reporting progress back to the GUI via
callbacks. Runs on a worker thread (see gui/processing_screen.py).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from .browser_automation import BrowserAutomation, AutomationError
from .database import Database
from .models import Customer
from .validator import OrderValidator

logger = logging.getLogger(__name__)


@dataclass
class Report:
    total: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0
    failures: List[tuple[int, str]] = field(default_factory=list)  # (customer_index, reason)

    def as_text(self) -> str:
        lines = [
            f"Customers Found: {self.total + self.skipped}",
            f"Orders Submitted: {self.success}",
            f"Failed: {self.failed}",
            f"Skipped: {self.skipped}",
        ]
        if self.failures:
            lines.append("")
            for idx, reason in self.failures:
                lines.append(f"Customer {idx}:\n{reason}\n")
        return "\n".join(lines)


class OrderProcessor:
    """Process a list of confirmed customers end to end."""

    def __init__(
        self,
        config: dict,
        db: Optional[Database] = None,
        batch_id: Optional[int] = None,
        on_progress: Optional[Callable[[int, int, str], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
        should_stop: Optional[Callable[[], bool]] = None,
    ):
        self.config = config
        self.db = db
        self.batch_id = batch_id
        self.validator = OrderValidator()
        self.on_progress = on_progress or (lambda done, total, msg: None)
        self.on_log = on_log or (lambda m: logger.info(m))
        self.should_stop = should_stop or (lambda: False)

    def process(self, customers: List[Customer]) -> Report:
        queue = [c for c in customers if c.status == "Confirmed"]
        report = Report(total=len(queue))
        report.skipped = sum(1 for c in customers if c.status == "Skipped")

        if not queue:
            self.on_log("No confirmed customers to process.")
            return report

        with BrowserAutomation(self.config, log_fn=self.on_log) as bot:
            for i, cust in enumerate(queue, start=1):
                if self.should_stop():
                    self.on_log("Processing stopped by user.")
                    break

                self.on_progress(i - 1, len(queue), f"Processing Customer {i}/{len(queue)}")
                self.on_log(f"Processing Customer {i}... ({cust.name} / {cust.phone})")

                reason = self._process_one(bot, cust)
                if reason is None:
                    cust.status = "Success"
                    report.success += 1
                    self.on_log(f"✓ Customer {i} order submitted")
                else:
                    cust.status = "Failed"
                    cust.failure_reason = reason
                    report.failed += 1
                    report.failures.append((i, reason))
                    self.on_log(f"⚠ Customer {i} failed: {reason}")

                if self.db and cust.id is not None:
                    self.db.update_customer_status(cust.id, cust.status, cust.failure_reason)

                self.on_progress(i, len(queue), f"Processed Customer {i}/{len(queue)}")

        if self.db and self.batch_id is not None:
            self.db.update_batch_counts(self.batch_id, report.total, report.success, report.failed)
        return report

    def _process_one(self, bot: BrowserAutomation, cust: Customer) -> Optional[str]:
        result = self.validator.validate(cust)
        if not result:
            return result.reason

        retries = self.config["automation"].get("retry_per_order", 1)
        last_error = "Unknown error"
        for attempt in range(1, retries + 2):
            try:
                bot.create_order(cust)
                return None
            except AutomationError as exc:
                last_error = str(exc)
                self.on_log(f"  attempt {attempt} failed: {last_error}")
            except Exception as exc:
                last_error = f"Unexpected error: {exc}"
                logger.exception("Unexpected error while processing customer")
                self.on_log(f"  attempt {attempt} error: {last_error}")
        return last_error
