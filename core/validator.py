"""Customer/order validation.

Runs before browser automation so we fail fast on obviously bad data and
record a clear reason for the report.
"""
from __future__ import annotations

import re

from .models import Customer, NOT_PROVIDED

_PHONE_OK = re.compile(r"^01[3-9]\d{8}$")


class ValidationResult:
    def __init__(self, ok: bool, reason: str = ""):
        self.ok = ok
        self.reason = reason

    def __bool__(self) -> bool:
        return self.ok


class OrderValidator:
    """Validate that a customer has enough information to be created."""

    def validate(self, cust: Customer) -> ValidationResult:
        if cust.phone == NOT_PROVIDED or not _PHONE_OK.match(cust.phone):
            return ValidationResult(False, "Missing or invalid phone number")
        if cust.address == NOT_PROVIDED or not cust.address.strip():
            return ValidationResult(False, "Missing address")
        if not cust.items:
            return ValidationResult(False, "No items")
        for idx, it in enumerate(cust.items, start=1):
            if not it.product.strip():
                return ValidationResult(False, f"Item {idx}: product name not assigned")
            if it.quantity < 1:
                return ValidationResult(False, f"Item {idx}: quantity must be at least 1")
        return ValidationResult(True)
