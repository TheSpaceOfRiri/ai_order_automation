# AI Order Automation Assistant

A modular **PyQt6 desktop application** that reduces manual order entry for an
online clothing business. It reads customer orders from PDFs, lets an operator
review/edit them, and uses **Playwright** to create the orders automatically on
[editionbreezy.com](https://editionbreezy.com/).

> Built to be extended: Messenger, WhatsApp, image-based product matching and
> automatic product detection can be added without touching the existing flow.

---

## Workflow

```
Upload PDF → Extract Customers (each with items[]) → Review/Edit
FOR EACH CUSTOMER:
    FOR EACH ITEM: search → open → color → size → qty → Add to Cart
    Open Cart → Checkout → fill info → select shipping → keep COD → Complete Order
    Wait for success → empty cart → next customer
→ Generate Report
```

One customer can buy multiple shirts, so all their items go into the cart and a
**single checkout** is completed per customer.

### Data structure

```
Customer { name, phone, address, city, shipping, payment, items[] }
Item     { product, color, size, quantity }
```

### Shipping detection

`Inside Dhaka` if the address/city (or an explicit `Shipping:` line) mentions
Dhaka/ঢাকা, otherwise `Outside Dhaka`. You can add a line to the PDF to force it:

```
Shipping: Inside Dhaka        (or)        Shipping: Outside Dhaka
```

---

## Folder structure

```
ai_order_automation/
├── main.py                     # entry point
├── config.example.json         # copy to config.json and fill credentials
├── requirements.txt
├── tests_parser.py             # standalone parser check
├── gui/
│   ├── main_window.py          # navigation + wiring of all screens
│   ├── review_screen.py        # editable order table (Confirm / Skip / Save)
│   ├── processing_screen.py    # progress bar + live logs (worker thread)
│   └── report_screen.py        # summary + export (TXT / CSV)
├── core/
│   ├── models.py               # Order dataclass (shared shape)
│   ├── pdf_reader.py           # pdfplumber wrapper
│   ├── order_parser.py         # Bengali/English parsing + business rules
│   ├── validator.py            # pre-automation validation
│   ├── browser_automation.py   # Playwright flow (edit SELECTORS here)
│   ├── order_processor.py      # batch orchestration + Report
│   └── database.py             # SQLite: orders, batches, logs, settings
├── reports/                    # exported reports
├── logs/                       # app.log + app.db (SQLite)
└── assets/
```

---

## Installation

```bash
cd ai_order_automation
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium      # downloads the browser Playwright drives

cp config.example.json config.json   # then edit credentials + selectors
python main.py
```

Quick sanity check of the parser without a GUI:

```bash
python tests_parser.py
```

---

## Configuration (`config.json`)

| Key | Meaning |
|-----|---------|
| `website.login_url` / `username` / `password` | admin login for editionbreezy.com |
| `business_rules.price_per_piece` | default **350**; drives the bill rule |
| `automation.headless` | `false` shows Chrome while it works |
| `automation.retry_per_order` | retries before an order is marked failed |

---

## The bill business rule

Price per piece is fixed (default **350 tk**). Expected total = `quantity × 350`.
If the **bill printed on the order is less** than the expected total, part was
paid in advance via Messenger, so the operator needs to collect the full amount.
The parser writes that amount into the **last name** field as `"<expected> taka
bill hobe"` (e.g. `1050 taka bill hobe` for 3 pcs). Configurable in
`core/order_parser.py::_apply_bill_rule`.

---

## Database schema (SQLite)

```
batches  (id, source_pdf, created_at, total, success, failed)
customers(id, batch_id, name, phone, address, city, shipping, payment,
          bill_amount, notes, status, failure_reason, raw_text, created_at)
items    (id, customer_id, product, color, size, quantity)
logs     (id, batch_id, customer_id, level, message, created_at)
settings (key, value)
```

`customers.status` ∈ `Pending | Confirmed | Skipped | Success | Failed`.
Querying `status NOT IN ('Success','Skipped')` gives **resume-after-interruption**
(`Database.pending_customers(batch_id)`).

---

## Class overview

```
MainWindow (dashboard: orders / status / success / failure)
    │  uses PDFReader ──> OrderParser ──> [Customer{items[]}]
    │                                        └─> Database (batch + customers + items)
    ├─> ReviewScreen        (expandable tree: edit customers & items, add/remove item)
    ├─> ProcessingScreen ──> ProcessingWorker(QThread)
    │                              └─> OrderProcessor
    │                                     ├─> OrderValidator
    │                                     └─> BrowserAutomation (Playwright, cart-based)
    └─> ReportScreen        (Report -> TXT/CSV)
```

---

## ⚠️ Bengali text in the order PDFs is corrupted at the source

The sample `Order_confirmtion.pdf` embeds Bengali with a broken font /
ToUnicode mapping. Every text extractor (pdfplumber, PyPDF2, even Acrobat
copy-paste) returns mojibake for Bengali — e.g. `মোঃ শামিম` → `জমাোঃ শারমম`.
This is **not** a parser bug; the correct characters simply aren't in the text
layer. What still works from those orders:

* ✅ Phone numbers (incl. Bengali digits), Bill, Payment
* ✅ The entire English item list (Product / Color / Size / Quantity)
* ✅ Dhaka detection (`ঢাকা` usually survives) → correct shipping zone
* ❌ Bengali **name** and **address** come out garbled

Two ways to handle it:

1. **Fix Bengali names/addresses in the Review screen** (default). English
   orders are perfect; for Bengali orders the operator corrects name + address
   before confirming. Everything else is pre-filled.
2. **Enable OCR** for correct Bengali automatically. Set in `config.json`:
   ```json
   "pdf": { "use_ocr": true, "ocr_lang": "ben+eng" }
   ```
   and install the OCR stack:
   ```bash
   pip install pytesseract pdf2image
   # system: tesseract-ocr, tesseract-ocr-ben, poppler-utils
   ```
   OCR renders each page to an image and reads the (correct) pixels. If the
   libraries aren't present, the app silently falls back to the text layer.

> Best long-term fix: if you control how these PDFs are generated, export them
> with a proper Unicode Bengali font — then no OCR is needed.

---

## ⚠️ Before real automation works: verify selectors

I could not inspect the logged-in admin pages of editionbreezy.com, so the CSS
selectors in `core/browser_automation.py` (`SELECTORS` dict) are sensible
placeholders. Capture the real ones once:

```bash
playwright codegen https://editionbreezy.com/admin/login
```

Click through login → search → product → color/size/qty → customer form →
submit, copy the generated selectors into the `SELECTORS` dict. Each step is an
isolated method, so updating one page never breaks the others.

---

## Extending later

| Feature | Where it plugs in |
|---------|-------------------|
| Messenger / WhatsApp ingestion | new reader alongside `pdf_reader.py`, feeding the same `OrderParser` |
| Image-based product matching | new module called from `ReviewScreen` to auto-fill `tshirt_name`/`color` |
| Automatic product detection | extend `OrderParser` + a product catalog table |
| Resume after crash | already supported via `Database.pending_orders(batch_id)` |
| Multi-user | add a `users` table + `batches.user_id` |
```
