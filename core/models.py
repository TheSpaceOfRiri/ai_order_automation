"""Data models shared across the application.

A single customer can buy MANY shirts, so the core shape is:

    Customer
      ├── name / phone / address / city / shipping / payment
      └── items[]  →  { product, color, size, quantity }

Keeping this shape in one place means the parser, GUI, database and
browser-automation layers all speak the same language. Add new fields here
(e.g. `messenger_id`, `whatsapp_number`) when future channels are integrated.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Optional

NOT_PROVIDED = "Not Provided"

# Shipping zones — the checkout page has one radio per zone.
INSIDE_DHAKA = "Inside Dhaka"
OUTSIDE_DHAKA = "Outside Dhaka"


@dataclass
class Item:
    """One product line within a customer's order."""

    product: str = ""
    color: str = ""
    size: str = NOT_PROVIDED
    quantity: int = 1

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Item":
        known = {f: data[f] for f in cls.__dataclass_fields__ if f in data}
        return cls(**known)


@dataclass
class Customer:
    """A customer plus every item they ordered."""

    # --- Extracted from PDF ---
    name: str = NOT_PROVIDED
    phone: str = NOT_PROVIDED
    address: str = NOT_PROVIDED
    city: str = NOT_PROVIDED
    shipping: str = NOT_PROVIDED          # INSIDE_DHAKA | OUTSIDE_DHAKA
    payment: str = "COD"
    bill_amount: Optional[int] = None
    notes: str = ""
    # Goes into the checkout "Last name" field. Normally "(messenger)"; becomes
    # "(<amount> takar bill hobe)" when a discount/advance is detected.
    last_name_marker: str = "(messenger)"
    items: List[Item] = field(default_factory=list)

    # --- Runtime status (set by the processor) ---
    status: str = "Pending"               # Pending | Confirmed | Skipped | Success | Failed
    failure_reason: str = ""

    # --- Bookkeeping ---
    raw_text: str = ""
    id: Optional[int] = None

    @property
    def total_quantity(self) -> int:
        return sum(max(1, it.quantity) for it in self.items) if self.items else 0

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Customer":
        known = {f: data[f] for f in cls.__dataclass_fields__ if f in data and f != "items"}
        cust = cls(**known)
        cust.items = [Item.from_dict(i) for i in data.get("items", [])]
        return cust
