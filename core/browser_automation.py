"""Browser automation for editionbreezy.com using Playwright.

Cart-based flow (one checkout per customer):

    FOR EACH ITEM:  search → open → color → size → quantity → add to cart
    THEN:           open cart → checkout → fill info → shipping → COD →
                    Complete Order → wait for success → empty cart

IMPORTANT — selectors:
    The CSS selectors below are placeholders based on a typical Shopify-style
    storefront (editionbreezy.com appears to be one). Because I cannot see the
    live pages, verify each selector once with:

        playwright codegen https://editionbreezy.com

    Then paste the correct values into the SELECTORS dict. Every step is an
    isolated method, so fixing one page never breaks the others.
"""
from __future__ import annotations

import logging
from typing import Callable, Optional

from playwright.sync_api import (
    Playwright, Browser, Page,
    TimeoutError as PWTimeoutError,
    sync_playwright,
)

from .models import Customer, Item, INSIDE_DHAKA

logger = logging.getLogger(__name__)

# Centralised selectors — the ONLY place you edit when the site markup changes.
# For swatch-style variant pickers use the "{value}" placeholder.
SELECTORS = {
    # search
    "search_url": "https://editionbreezy.com/search?q={query}",
    "search_result_first": "a.full-unstyled-link, .card__heading a, .product-item a",
    # product page variants
    "color_option": "select[name='Color'], .product-form__input input[value='{value}'] + label, [data-option-name='Color'] [data-value='{value}']",
    "size_option": "select[name='Size'], .product-form__input input[value='{value}'] + label, [data-option-name='Size'] [data-value='{value}']",
    "quantity_input": "input[name='quantity'], .quantity__input",
    "add_to_cart": "button[name='add'], .product-form__submit",
    # cart / checkout — matched to the real editionbreezy.com Shopify checkout
    "cart_url": "https://editionbreezy.com/cart",
    "checkout_button": "button[name='checkout'], input[name='checkout'], #checkout, a[href='/checkout']",
    # "Email or mobile phone number" (Contact). We put the phone here.
    "co_email": "#email, input[name='email'], input[autocomplete='email']",
    # Delivery: First name (optional) + Last name (required).
    "co_first_name": "input[name='firstName'], input[autocomplete='given-name'], #TextField-firstName",
    "co_last_name": "input[name='lastName'], input[autocomplete='family-name'], #TextField-lastName",
    "co_address": "input[name='address1'], input[autocomplete='address-line1'], #shipping-address1",
    "co_city": "input[name='city'], input[autocomplete='address-level2']",
    "co_phone": "input[name='phone'], input[autocomplete='tel']",
    # Country/Region is preset to Bangladesh; set defensively if needed.
    "co_country": "select[name='countryCode'], select[autocomplete='country']",
    # Shipping method radios: labels read "Inside Dhaka" / "Outside Dhaka".
    "shipping_option": "label:has-text('{value}'), text={value}",
    # Payment: "Cash on Delivery (COD)" is preselected on this store.
    "cod_option": "text=Cash on Delivery",
    "complete_order": "#checkout-pay-button, button:has-text('Complete order')",
    "order_confirmation": "text=Thank you, text=order is confirmed, .os-step__title",
    # empty cart (fallback after success)
    "cart_remove": "cart-remove-button a, a.cart-item__remove, button[aria-label*='Remove']",
}


class AutomationError(Exception):
    """Raised when a step fails such that the current customer should abort."""


class BrowserAutomation:
    """Drives a real Chromium browser to create orders, cart-first."""

    def __init__(self, config: dict, log_fn: Optional[Callable[[str], None]] = None):
        self.cfg = config
        self.web = config["website"]
        self.auto = config["automation"]
        self._log = log_fn or (lambda m: logger.info(m))
        self._pw: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None

    # --------------------------------------------------------------- #
    def start(self) -> None:
        self._log("Launching Chromium…")
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=self.auto.get("headless", False),
            slow_mo=self.auto.get("slow_mo_ms", 0),
        )
        self._page = self._browser.new_page()
        self._page.set_default_timeout(self.auto.get("page_timeout_ms", 30000))

    def stop(self) -> None:
        try:
            if self._browser:
                self._browser.close()
            if self._pw:
                self._pw.stop()
        except Exception as exc:
            logger.warning("Error during browser shutdown: %s", exc)

    def __enter__(self) -> "BrowserAutomation":
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.stop()

    # --------------------------------------------------------------- #
    # Full per-customer flow
    # --------------------------------------------------------------- #
    def create_order(self, cust: Customer) -> None:
        """Add every item to the cart, then check out once. Raises
        AutomationError (with a readable reason) on failure."""
        self._empty_cart()  # start clean so no leftovers from a prior customer

        for i, item in enumerate(cust.items, start=1):
            self._log(f"  Item {i}/{len(cust.items)}: {item.product}")
            self._add_item_to_cart(item)
            self._log(f"  ✓ {item.product} added")

        self._open_cart()
        self._start_checkout()
        self._fill_customer(cust)
        self._select_shipping(cust)
        self._keep_cod_selected()
        self._complete_order()
        self._log("  ✓ Order submitted")

    # ---- per item ---- #
    def _add_item_to_cart(self, item: Item) -> None:
        self._search_product(item)
        self._open_first_result(item)
        self._select_variant("color_option", item.color, "Color unavailable")
        self._select_variant("size_option", item.size, "Size unavailable")
        self._set_quantity(item)
        try:
            self._page.click(SELECTORS["add_to_cart"])
            self._page.wait_for_load_state("networkidle")
        except PWTimeoutError:
            raise AutomationError(f"Could not add '{item.product}' to cart")

    def _search_product(self, item: Item) -> None:
        url = SELECTORS["search_url"].format(query=item.product.replace(" ", "+"))
        self._page.goto(url)
        self._page.wait_for_load_state("networkidle")

    def _open_first_result(self, item: Item) -> None:
        try:
            self._page.wait_for_selector(SELECTORS["search_result_first"], timeout=8000)
            self._page.click(SELECTORS["search_result_first"])
            self._page.wait_for_load_state("networkidle")
        except PWTimeoutError:
            raise AutomationError("Product not found")

    def _select_variant(self, key: str, value: str, err: str) -> None:
        if not value or value == "Not Provided":
            return
        if not self._try_select_or_click(key, value):
            raise AutomationError(err)

    def _set_quantity(self, item: Item) -> None:
        try:
            self._page.fill(SELECTORS["quantity_input"], str(item.quantity), timeout=4000)
        except PWTimeoutError:
            self._log("  quantity field not found; leaving default")

    # ---- checkout ---- #
    def _open_cart(self) -> None:
        self._page.goto(SELECTORS["cart_url"])
        self._page.wait_for_load_state("networkidle")

    def _start_checkout(self) -> None:
        try:
            self._page.click(SELECTORS["checkout_button"])
            self._page.wait_for_load_state("networkidle")
        except PWTimeoutError:
            raise AutomationError("Checkout button not found")

    def _fill_customer(self, cust: Customer) -> None:
        self._log("  Filling customer information…")
        self._safe_fill("co_email", cust.phone)          # "Email or mobile phone number"

        # The operator's convention: the FULL customer name goes in "First name",
        # and "Last name" carries the marker — "(messenger)" normally, or
        # "(<amount> takar bill hobe)" when a discount was applied.
        name = "" if cust.name == "Not Provided" else cust.name.strip()
        self._safe_fill("co_first_name", name)
        self._safe_fill("co_last_name", cust.last_name_marker)

        self._safe_fill("co_address", cust.address if cust.address != "Not Provided" else "")
        self._safe_fill("co_city", cust.city if cust.city != "Not Provided" else "")
        self._safe_fill("co_phone", cust.phone)
        self._log(f"  ✓ Customer info filled (last name: {cust.last_name_marker})")

    def _select_shipping(self, cust: Customer) -> None:
        """Operator's rule: the Inside/Outside Dhaka choice only matters for
        SINGLE-item orders. For multi-item orders leave the page default
        (Inside Dhaka) untouched, exactly as done manually."""
        if len(cust.items) != 1:
            self._log("  (multi-item order — leaving shipping on default)")
            return
        label = cust.shipping if cust.shipping in (INSIDE_DHAKA, "Outside Dhaka") else INSIDE_DHAKA
        # A shipping_option value may contain a comma-separated fallback list.
        for cand in SELECTORS["shipping_option"].split(","):
            try:
                self._page.click(cand.strip().format(value=label), timeout=5000)
                self._log(f"  ✓ {label} selected")
                return
            except PWTimeoutError:
                continue
        self._log(f"  ⚠ shipping option '{label}' not found; using page default")

    def _keep_cod_selected(self) -> None:
        # COD is usually preselected; click defensively, ignore if absent.
        try:
            self._page.click(SELECTORS["cod_option"], timeout=3000)
        except Exception:
            pass

    def _complete_order(self) -> None:
        try:
            self._page.click(SELECTORS["complete_order"])
            self._page.wait_for_selector(SELECTORS["order_confirmation"], timeout=20000)
        except PWTimeoutError:
            raise AutomationError("Order not confirmed (Complete Order failed)")

    # ---- housekeeping ---- #
    def _empty_cart(self) -> None:
        try:
            self._page.goto(SELECTORS["cart_url"])
            self._page.wait_for_load_state("networkidle")
            while True:
                btn = self._page.query_selector(SELECTORS["cart_remove"])
                if not btn:
                    break
                btn.click()
                self._page.wait_for_load_state("networkidle")
        except Exception:
            pass  # best-effort; empty cart is not fatal

    # ---- helpers ---- #
    def _try_select_or_click(self, key: str, value: str) -> bool:
        """Handle native <select> dropdowns and swatch/label buttons."""
        sel = SELECTORS[key]
        candidates = [s.strip() for s in sel.split(",")]
        for cand in candidates:
            filled = cand.format(value=value) if "{value}" in cand else cand
            try:
                if filled.startswith("select"):
                    self._page.select_option(filled, label=value, timeout=2500)
                else:
                    self._page.click(filled, timeout=2500)
                return True
            except Exception:
                continue
        return False

    def _safe_fill(self, key: str, value: str) -> bool:
        try:
            self._page.fill(SELECTORS[key], value or "", timeout=4000)
            return True
        except Exception:
            self._log(f"  field '{key}' not found; skipped")
            return False
