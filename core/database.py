"""SQLite persistence for customers, items, batches, logs and settings.

Gives us resumable processing, an audit trail, and a home for future
multi-user data.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .models import Customer, Item

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS batches (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source_pdf  TEXT,
    created_at  TEXT,
    total       INTEGER DEFAULT 0,
    success     INTEGER DEFAULT 0,
    failed      INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS customers (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id       INTEGER,
    name           TEXT,
    phone          TEXT,
    address        TEXT,
    city           TEXT,
    shipping       TEXT,
    payment        TEXT,
    bill_amount    INTEGER,
    notes          TEXT,
    last_name_marker TEXT DEFAULT '(messenger)',
    status         TEXT DEFAULT 'Pending',
    failure_reason TEXT DEFAULT '',
    raw_text       TEXT,
    created_at     TEXT
);

CREATE TABLE IF NOT EXISTS items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER,
    product     TEXT,
    color       TEXT,
    size        TEXT,
    quantity    INTEGER,
    FOREIGN KEY (customer_id) REFERENCES customers(id)
);

CREATE TABLE IF NOT EXISTS logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id    INTEGER,
    customer_id INTEGER,
    level       TEXT,
    message     TEXT,
    created_at  TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


class Database:
    def __init__(self, db_path: str = "logs/app.db"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # ---------------- Batches ---------------- #
    def create_batch(self, source_pdf: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO batches (source_pdf, created_at) VALUES (?, ?)",
            (source_pdf, datetime.now().isoformat()),
        )
        self.conn.commit()
        return cur.lastrowid

    def update_batch_counts(self, batch_id: int, total: int, success: int, failed: int) -> None:
        self.conn.execute(
            "UPDATE batches SET total=?, success=?, failed=? WHERE id=?",
            (total, success, failed, batch_id),
        )
        self.conn.commit()

    # ---------------- Customers + items ---------------- #
    def save_customers(self, batch_id: int, customers: List[Customer]) -> None:
        for c in customers:
            cur = self.conn.execute(
                """INSERT INTO customers
                   (batch_id, name, phone, address, city, shipping, payment,
                    bill_amount, notes, last_name_marker, status, failure_reason,
                    raw_text, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (batch_id, c.name, c.phone, c.address, c.city, c.shipping,
                 c.payment, c.bill_amount, c.notes, c.last_name_marker, c.status,
                 c.failure_reason, c.raw_text, datetime.now().isoformat()),
            )
            c.id = cur.lastrowid
            for it in c.items:
                self.conn.execute(
                    "INSERT INTO items (customer_id, product, color, size, quantity) VALUES (?,?,?,?,?)",
                    (c.id, it.product, it.color, it.size, it.quantity),
                )
        self.conn.commit()

    def update_customer_status(self, customer_id: int, status: str, reason: str = "") -> None:
        self.conn.execute(
            "UPDATE customers SET status=?, failure_reason=? WHERE id=?",
            (status, reason, customer_id),
        )
        self.conn.commit()

    def pending_customers(self, batch_id: int) -> List[Customer]:
        """Resume-after-interruption: everything not yet Success/Skipped."""
        rows = self.conn.execute(
            "SELECT * FROM customers WHERE batch_id=? AND status NOT IN ('Success','Skipped')",
            (batch_id,),
        ).fetchall()
        result = []
        for r in rows:
            cust = Customer.from_dict(dict(r))
            item_rows = self.conn.execute(
                "SELECT * FROM items WHERE customer_id=?", (r["id"],)
            ).fetchall()
            cust.items = [Item.from_dict(dict(ir)) for ir in item_rows]
            result.append(cust)
        return result

    # ---------------- Logs / settings ---------------- #
    def log(self, batch_id: Optional[int], customer_id: Optional[int], level: str, message: str) -> None:
        self.conn.execute(
            "INSERT INTO logs (batch_id, customer_id, level, message, created_at) VALUES (?,?,?,?,?)",
            (batch_id, customer_id, level, message, datetime.now().isoformat()),
        )
        self.conn.commit()

    def set_setting(self, key: str, value) -> None:
        self.conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, json.dumps(value)),
        )
        self.conn.commit()

    def get_setting(self, key: str, default=None):
        row = self.conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return json.loads(row["value"]) if row else default

    def close(self) -> None:
        self.conn.close()
