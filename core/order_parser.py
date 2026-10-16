"""Order parsing: turn raw PDF text into structured `Customer` objects.

Tuned for the real PDF format:

    **Order confirmed ✅**
    Name, Phone Number, Address ⬇️

    Name : Sunny                    (or)   নাম: জাবেদ   (or)   bare name line
    Address : 250/2, ..., Rajshahi  (or)   ঠিকানা: ...  (or)   multi-line address
    Mobile No : 01749462068         (or)   ফোন নাঃ ...  (or)   bare phone line

    Bill: 820 taka cash on delivery ✅
    Note:

    Items:
    1. Product: Lost
       Color: Black
       Size: L
       Quantity: 1
    2. Product: Pokemon
       ...

Handles Bengali/English digits, phone de-duplication, multiple items per
customer, city + shipping detection, and the price-per-piece bill rule.
"""
from __future__ import annotations

import logging
import re
from typing import List

from .models import Customer, Item, NOT_PROVIDED, INSIDE_DHAKA, OUTSIDE_DHAKA

logger = logging.getLogger(__name__)

# Bengali -> ASCII digits.
_BENGALI_DIGITS = "০১২৩৪৫৬৭৮৯"
_ASCII_DIGITS = "0123456789"
_DIGIT_TABLE = str.maketrans(_BENGALI_DIGITS, _ASCII_DIGITS)

_PHONE_RE = re.compile(r"(?:\+?88)?0?1[3-9]\d{8}")
_BILL_RE = re.compile(r"bill\D{0,6}(\d{2,6})", re.IGNORECASE)

# Labels (English + Bengali).
_NAME_LABEL = re.compile(r"^\s*(?:name|নাম)\s*[:：\-]\s*(.+)$", re.IGNORECASE)
_ADDR_LABEL = re.compile(r"^\s*(?:address|ঠিকানা)\s*[:：\-]?\s*(.*)$", re.IGNORECASE)
_PHONE_LABEL = re.compile(r"^\s*(?:mobile\s*no|mobile|phone|ফোন\s*না?ঃ?)\s*[:：\-]?\s*(.*)$",
                          re.IGNORECASE)

# Structured item block: Product / Color / Size / Quantity (in that order).
_ITEM_RE = re.compile(
    r"product\s*[:\-]\s*(?P<product>.+?)\s*[\r\n]+"
    r"\s*colou?r\s*[:\-]\s*(?P<color>.+?)\s*[\r\n]+"
    r"\s*size\s*[:\-]\s*(?P<size>.+?)\s*[\r\n]+"
    r"\s*(?:quantity|qty)\s*[:\-]\s*(?P<qty>\d+)",
    re.IGNORECASE)

# Loose fallback item scanner (older "T-shirt N pcs" style).
_QTY_RE = re.compile(r"(\d+)\s*(?:pcs|piece|pc|টি|পিস)", re.IGNORECASE)
_SIZE_RE = re.compile(r"size\s*[:\-]?\s*([A-Za-z0-9]+)", re.IGNORECASE)
_TNAME_RE = re.compile(r"tshirt\s*name\s*[:\-]?\s*(.*)", re.IGNORECASE)
_COLOR_RE = re.compile(r"colou?r\s*[:\-]?\s*(.*)", re.IGNORECASE)

_DHAKA_RE = re.compile(r"dhaka|ঢাকা", re.IGNORECASE)

# Common districts/cities to fill the checkout "City" field. Extend freely.
_KNOWN_CITIES = [
    "Dhaka", "Chittagong", "Chattogram", "Rajshahi", "Khulna", "Sylhet",
    "Barisal", "Rangpur", "Mymensingh", "Bogura", "Bogra", "Comilla",
    "Cumilla", "Narayanganj", "Gazipur", "Bhola", "Jessore", "Jashore",
    "Cox's Bazar", "Tangail", "Dinajpur", "Pabna", "Kushtia", "Feni",
    "Noakhali", "Faridpur", "Kishoreganj", "Naogaon", "Natore", "Jamalpur",
]
# Bengali district hints -> canonical English city.
_BENGALI_CITY = {
    "ঢাকা": "Dhaka", "ভোলা": "Bhola", "চট্টগ্রাম": "Chittagong",
    "রাজশাহী": "Rajshahi", "বগুড়া": "Bogura", "খুলনা": "Khulna",
    "সিলেট": "Sylhet", "রংপুর": "Rangpur", "বরিশাল": "Barisal",
}


class OrderParser:
    """Parse a block of PDF text into a list of `Customer`s."""

    def __init__(self, price_per_piece: int = 350, default_payment: str = "COD",
                 messenger_marker: str = "(messenger)",
                 bill_note_template: str = "({amount} takar bill hobe)"):
        self.price_per_piece = price_per_piece
        self.default_payment = default_payment
        self.messenger_marker = messenger_marker
        self.bill_note_template = bill_note_template

    # ------------------------------------------------------------------ #
    def parse(self, text: str) -> List[Customer]:
        text = self.normalize_digits(text)
        blocks = self._split_into_customers(text)
        logger.info("Detected %d candidate customer block(s).", len(blocks))

        customers: List[Customer] = []
        seen_phones: set[str] = set()

        for block in blocks:
            if not block.strip():
                continue
            cust = self._parse_block(block)
            if cust.phone != NOT_PROVIDED:
                if cust.phone in seen_phones:
                    logger.info("Skipping duplicate phone: %s", cust.phone)
                    continue
                seen_phones.add(cust.phone)
            # Ignore stray blocks with neither phone nor items.
            if cust.phone == NOT_PROVIDED and not any(i.product for i in cust.items):
                continue
            customers.append(cust)

        return customers

    # ------------------------------------------------------------------ #
    @staticmethod
    def normalize_digits(text: str) -> str:
        return text.translate(_DIGIT_TABLE)

    def _split_into_customers(self, text: str) -> List[str]:
        """Split on the "Order confirmed" marker (primary), then fallbacks."""
        if re.search(r"order\s+confirmed", text, re.IGNORECASE):
            parts = re.split(r"(?im)^\s*\**\s*order\s+confirmed.*$", text)
            return [p.strip() for p in parts if p.strip()]

        if re.search(r"first\s*name", text, re.IGNORECASE):
            parts = re.split(r"(?i)(?=first\s*name)", text)
            return [p.strip() for p in parts if p.strip()]

        # Fallback: a line of only dashes separates records.
        if re.search(r"(?m)^\s*-{3,}\s*$", text):
            return [p.strip() for p in re.split(r"(?m)^\s*-{3,}\s*$", text) if p.strip()]

        # Last resort: split so each block ends after a phone number.
        blocks, current = [], []
        for line in text.splitlines():
            current.append(line)
            if _PHONE_RE.search(line):
                blocks.append("\n".join(current))
                current = []
        if current and any(l.strip() for l in current):
            blocks.append("\n".join(current))
        return [b.strip() for b in blocks if b.strip()] or ([text] if text.strip() else [])

    def _parse_block(self, block: str) -> Customer:
        cust = Customer(raw_text=block)

        name, address, phone = self._extract_customer_info(block)
        cust.name = name
        cust.address = address
        cust.phone = phone
        cust.city = self._extract_city(block, address)
        cust.shipping = self._extract_shipping(block, address, cust.city)
        cust.bill_amount = self._extract_bill(block)
        cust.payment = self._extract_payment(block)
        cust.items = self._extract_items(block)
        cust.notes = self._extract_notes(block)

        self._apply_bill_rule(cust)
        return cust

    # ------------------------------------------------------------------ #
    def _extract_customer_info(self, block: str) -> tuple[str, str, str]:
        """Parse the customer region (everything before Bill/Items/Note).

        Strategy: within that region, phone lines are pulled out, an explicit
        Name/Address label wins, and any remaining unlabeled lines become the
        name (first one) then the address (the rest). This handles labeled,
        Bengali, and bare multi-line-address variants uniformly.
        """
        lines = block.splitlines()

        # Find where the customer region ends.
        end = len(lines)
        for i, line in enumerate(lines):
            if re.match(r"\s*(?:bill|items?|note)\s*[:：]", line, re.IGNORECASE):
                end = i
                break
        region = lines[:end]

        phone = NOT_PROVIDED
        name = ""
        addr_parts: List[str] = []

        for raw in region:
            line = raw.strip()
            if not line:
                continue
            # Skip the boilerplate header line.
            if re.search(r"name\s*,\s*phone", line, re.IGNORECASE):
                continue

            # Any line containing a phone number is treated as the phone line
            # and dropped — labels may be garbled (e.g. Bengali "ফোন নাঃ"
            # extracts as "জিান নাোঃ"), so we must not rely on matching them.
            pm = _PHONE_RE.search(line)
            if pm:
                if phone == NOT_PROVIDED:
                    phone = self._normalize_phone(pm.group())
                continue

            m = _NAME_LABEL.match(line)
            if m:
                name = name or m.group(1).strip()
                continue

            m = _ADDR_LABEL.match(line)
            if m:
                val = m.group(1).strip()
                if val:
                    addr_parts.append(val)
                continue

            if _PHONE_LABEL.match(line):  # label with no captured number
                continue

            # Unlabeled line: first one is the name, the rest are address.
            if not name:
                name = line
            else:
                addr_parts.append(line)

        return (name or NOT_PROVIDED,
                ", ".join(addr_parts) if addr_parts else NOT_PROVIDED,
                phone)

    @staticmethod
    def _is_phone_line(line: str) -> bool:
        """True if the line is essentially just a phone number."""
        digits = re.sub(r"\D", "", line)
        stripped = re.sub(r"[\s\+\-()]", "", line)
        return len(digits) >= 10 and len(stripped) - len(digits) <= 2

    @staticmethod
    def _normalize_phone(raw: str) -> str:
        digits = re.sub(r"\D", "", raw)
        if digits.startswith("88") and len(digits) > 11:
            digits = digits[2:]
        if len(digits) == 10 and digits.startswith("1"):
            digits = "0" + digits
        return digits

    def _extract_city(self, block: str, address: str) -> str:
        m = re.search(r"city\s*[:\-]\s*(.+)", block, re.IGNORECASE)
        if m and m.group(1).strip():
            return m.group(1).strip().splitlines()[0].strip()
        hay = f"{address} {block}"
        for city in _KNOWN_CITIES:
            if re.search(rf"\b{re.escape(city)}\b", hay, re.IGNORECASE):
                return "Bogura" if city.lower() == "bogra" else city
        for bn, en in _BENGALI_CITY.items():
            if bn in hay:
                return en
        return NOT_PROVIDED

    def _extract_shipping(self, block: str, address: str, city: str) -> str:
        m = re.search(r"shipping\s*[:\-]\s*(.+)", block, re.IGNORECASE)
        if m and m.group(1).strip():
            value = m.group(1)
            if re.search(r"outside|বাহির|বাইরে", value, re.IGNORECASE):
                return OUTSIDE_DHAKA
            return INSIDE_DHAKA if _DHAKA_RE.search(value) else OUTSIDE_DHAKA
        return INSIDE_DHAKA if _DHAKA_RE.search(f"{city} {address}") else OUTSIDE_DHAKA

    def _extract_bill(self, block: str) -> int | None:
        m = _BILL_RE.search(block)
        return int(m.group(1)) if m else None

    def _extract_payment(self, block: str) -> str:
        low = block.lower()
        if "cash on delivery" in low or "cod" in low:
            return "COD"
        if "bkash" in low or "বিকাশ" in low:
            return "bKash"
        if "nagad" in low or "নগদ" in low:
            return "Nagad"
        return self.default_payment

    def _extract_items(self, block: str) -> List[Item]:
        """Structured Product/Color/Size/Quantity blocks, with a loose fallback."""
        items = [
            Item(product=m.group("product").strip(),
                 color=m.group("color").strip(),
                 size=m.group("size").strip().upper(),
                 quantity=int(m.group("qty")))
            for m in _ITEM_RE.finditer(block)
        ]
        if items:
            return items
        return self._extract_items_loose(block)

    def _extract_items_loose(self, block: str) -> List[Item]:
        items: List[Item] = []
        cur: Item | None = None

        def ensure() -> Item:
            nonlocal cur
            if cur is None:
                cur = Item()
            return cur

        # Only scan the region after "Items:" if present, else whole block.
        m = re.search(r"items?\s*[:：]", block, re.IGNORECASE)
        scan = block[m.end():] if m else block

        for raw in scan.splitlines():
            line = raw.strip()
            if not line:
                continue
            qty_m = _QTY_RE.search(line)
            name_m = _TNAME_RE.search(line)
            size_m = _SIZE_RE.search(line)
            color_m = _COLOR_RE.search(line)

            if qty_m:
                if cur is not None:
                    items.append(cur)
                cur = Item(quantity=int(qty_m.group(1)))
                if size_m:
                    cur.size = size_m.group(1).upper()
                continue
            if name_m:
                ensure().product = name_m.group(1).strip()
                continue
            if size_m:
                ensure().size = size_m.group(1).upper()
                continue
            if color_m:
                ensure().color = color_m.group(1).strip()
                continue

        if cur is not None:
            items.append(cur)
        return items or [Item(quantity=1)]

    def _extract_notes(self, block: str) -> str:
        # [ \t]* (not \s*) so we never cross the newline into the "Items:" line.
        m = re.search(r"note[ \t]*[:：][ \t]*([^\r\n]*)", block, re.IGNORECASE)
        note = m.group(1).strip() if m else ""
        # Ignore the empty "Note:" placeholder.
        return note if note and note.lower() != "note" else ""

    def _apply_bill_rule(self, cust: Customer) -> None:
        """Decide what goes in the checkout "Last name" field.

        Standard total = total_qty * price_per_piece. If the stated bill is LESS
        (a discount / advance was given), the Last name carries the amount to
        collect at delivery, e.g. "(1000 takar bill hobe)". Otherwise it stays
        "(messenger)".
        """
        expected = cust.total_quantity * self.price_per_piece
        if (cust.bill_amount is not None and expected > 0
                and cust.bill_amount < expected):
            cust.last_name_marker = self.bill_note_template.format(amount=cust.bill_amount)
            logger.info("Discount detected: stated %s < standard %s -> last name '%s'",
                        cust.bill_amount, expected, cust.last_name_marker)
        else:
            cust.last_name_marker = self.messenger_marker
