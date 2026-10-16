"""Review screen: an expandable tree of customers and their items.

Top-level rows are customers (editable info). Each customer expands to show its
items (editable product/color/size/qty). Operators can add/remove items and
Confirm / Skip each customer. Only Confirmed customers are automated.
"""
from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QHeaderView, QLabel,
)

from core.models import Customer, Item, NOT_PROVIDED

# Tree columns serve both customer rows and item rows.
# Customer row:  Name, Last-name marker, Phone, Address, City, Shipping, Payment, Status
# Item row:      Product, Color, Size, Quantity  (first four columns)
COLUMNS = ["Name / Product", "Last Name / Color", "Phone / Size",
           "Address / Qty", "City", "Shipping", "Payment", "Status"]
STATUS_COL = 7

CUSTOMER = 0  # QTreeWidgetItem.type() markers
ITEM = 1


class ReviewScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.customers: List[Customer] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Review & Edit — double-click any cell to edit. Expand a customer "
            "to see items. Confirm or Skip each customer before processing."))

        self.tree = QTreeWidget()
        self.tree.setColumnCount(len(COLUMNS))
        self.tree.setHeaderLabels(COLUMNS)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tree.setEditTriggers(QTreeWidget.EditTrigger.DoubleClicked
                                  | QTreeWidget.EditTrigger.SelectedClicked)
        layout.addWidget(self.tree)

        row = QHBoxLayout()
        self.add_item_btn = QPushButton("Add Item")
        self.remove_item_btn = QPushButton("Remove Item")
        self.confirm_btn = QPushButton("Confirm Selected")
        self.skip_btn = QPushButton("Skip Selected")
        self.confirm_all_btn = QPushButton("Confirm All")
        self.save_btn = QPushButton("Save Changes")
        for b in (self.add_item_btn, self.remove_item_btn, self.confirm_btn,
                  self.skip_btn, self.confirm_all_btn, self.save_btn):
            row.addWidget(b)
        layout.addLayout(row)

        self.add_item_btn.clicked.connect(self._add_item)
        self.remove_item_btn.clicked.connect(self._remove_item)
        self.confirm_btn.clicked.connect(lambda: self._set_status_selected("Confirmed"))
        self.skip_btn.clicked.connect(lambda: self._set_status_selected("Skipped"))
        self.confirm_all_btn.clicked.connect(self._confirm_all)
        self.save_btn.clicked.connect(self.save_changes)

    # ------------------------------------------------------------------ #
    def load_customers(self, customers: List[Customer]) -> None:
        self.customers = customers
        self.tree.clear()
        for c in customers:
            self.tree.addTopLevelItem(self._make_customer_node(c))
        self.tree.expandAll()

    def _make_customer_node(self, c: Customer) -> QTreeWidgetItem:
        node = QTreeWidgetItem(
            [c.name, c.last_name_marker, c.phone, c.address, c.city,
             c.shipping, c.payment, c.status],
            CUSTOMER)
        node.setFlags(node.flags() | Qt.ItemFlag.ItemIsEditable)
        for it in c.items:
            node.addChild(self._make_item_node(it))
        return node

    def _make_item_node(self, it: Item) -> QTreeWidgetItem:
        child = QTreeWidgetItem(
            [it.product, it.color, it.size, str(it.quantity), "", "", "", ""], ITEM)
        child.setFlags(child.flags() | Qt.ItemFlag.ItemIsEditable)
        return child

    # ------------------------------------------------------------------ #
    def save_changes(self) -> None:
        """Push edits from the tree back into the Customer/Item objects."""
        for i in range(self.tree.topLevelItemCount()):
            node = self.tree.topLevelItem(i)
            c = self.customers[i]
            c.name = node.text(0).strip() or NOT_PROVIDED
            c.last_name_marker = node.text(1).strip() or "(messenger)"
            c.phone = node.text(2).strip() or NOT_PROVIDED
            c.address = node.text(3).strip() or NOT_PROVIDED
            c.city = node.text(4).strip() or NOT_PROVIDED
            c.shipping = node.text(5).strip() or NOT_PROVIDED
            c.payment = node.text(6).strip() or "COD"

            c.items = []
            for j in range(node.childCount()):
                child = node.child(j)
                qty_txt = child.text(3).strip()
                c.items.append(Item(
                    product=child.text(0).strip(),
                    color=child.text(1).strip(),
                    size=child.text(2).strip() or NOT_PROVIDED,
                    quantity=int(qty_txt) if qty_txt.isdigit() else 1,
                ))

    # ------------------------------------------------------------------ #
    def _selected_customer_node(self) -> Optional[QTreeWidgetItem]:
        item = self.tree.currentItem()
        if item is None:
            return None
        return item if item.type() == CUSTOMER else item.parent()

    def _add_item(self) -> None:
        node = self._selected_customer_node()
        if node is None:
            return
        node.addChild(self._make_item_node(Item(product="New Product", quantity=1)))
        node.setExpanded(True)

    def _remove_item(self) -> None:
        item = self.tree.currentItem()
        if item is not None and item.type() == ITEM:
            item.parent().removeChild(item)

    def _set_status_selected(self, status: str) -> None:
        self.save_changes()
        for i in range(self.tree.topLevelItemCount()):
            node = self.tree.topLevelItem(i)
            if node.isSelected() or (self.tree.currentItem()
                                     and self._selected_customer_node() is node):
                self.customers[i].status = status
                node.setText(STATUS_COL, status)

    def _confirm_all(self) -> None:
        self.save_changes()
        for i in range(self.tree.topLevelItemCount()):
            node = self.tree.topLevelItem(i)
            if self.customers[i].status != "Skipped":
                self.customers[i].status = "Confirmed"
            node.setText(STATUS_COL, self.customers[i].status)
