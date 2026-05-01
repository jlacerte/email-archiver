# Invoice Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a two-phase invoice extraction system (scan + download) to identify Gmail subscriptions, download PDF invoices, and generate monthly CSV summaries for the accountant.

**Architecture:** Two new modules (`invoice_scanner.py`, `invoice_downloader.py`) following the same patterns as `archiver.py` and `organizer.py`. Phase 1 does a read-only two-pass scan (headers first, then full messages for matches only). Phase 2 downloads PDFs and generates CSV. One new method added to `IMAPClient`.

**Tech Stack:** Python 3.13 stdlib only — `email`, `email.utils`, `csv`, `json`, `mimetypes`, `datetime`. Tests use `unittest` + `unittest.mock`. Run tests with `/opt/homebrew/bin/python3.13 -m unittest discover -s tests -v`.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `email_archiver/imap_client.py` | Modify | Add `fetch_message(uid)` method |
| `tests/test_imap_client.py` | Modify | Add tests for `fetch_message()` |
| `email_archiver/invoice_scanner.py` | Create | Invoice patterns, classification, two-pass scan, report generation |
| `tests/test_invoice_scanner.py` | Create | Tests for classification, provider resolution, report building |
| `email_archiver/invoice_downloader.py` | Create | PDF extraction, file naming, CSV generation, download orchestration |
| `tests/test_invoice_downloader.py` | Create | Tests for PDF extraction, naming, CSV output |
| `email_archiver/cli.py` | Modify | Add `invoices` subcommand with `scan` and `download` actions |
| `tests/test_cli.py` | Create | Tests for CLI argument parsing |

---

### Task 1: Add `fetch_message()` to IMAPClient

**Files:**
- Modify: `email_archiver/imap_client.py`
- Modify: `tests/test_imap_client.py`

- [ ] **Step 1: Write the failing test for `fetch_message()` success**

Add to `tests/test_imap_client.py`:

```python
class TestFetchMessage(unittest.TestCase):

    @patch("email_archiver.imap_client.imaplib.IMAP4_SSL")
    def test_fetch_message_success(self, mock_ssl):
        """fetch_message returns a parsed email.message.Message on success."""
        raw_email = (
            b"From: billing@anthropic.com\r\n"
            b"Subject: Your invoice\r\n"
            b"Date: Thu, 01 Apr 2026 10:00:00 +0000\r\n"
            b"Content-Type: text/plain\r\n"
            b"\r\n"
            b"Here is your invoice.\r\n"
        )
        mock_conn = MagicMock()
        mock_conn.uid.return_value = ("OK", [
            (b"1 (UID 4532 BODY[] {123}", raw_email),
            b")",
        ])
        mock_ssl.return_value = mock_conn

        client = IMAPClient("imap.test.com", 993, "user", "pass")
        client.connect()
        msg = client.fetch_message(b"4532")

        self.assertIsNotNone(msg)
        self.assertIn("anthropic", msg["From"])
        self.assertEqual(msg["Subject"], "Your invoice")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/opt/homebrew/bin/python3.13 -m unittest tests.test_imap_client.TestFetchMessage.test_fetch_message_success -v`

Expected: `AttributeError: 'IMAPClient' object has no attribute 'fetch_message'`

- [ ] **Step 3: Write the failing test for `fetch_message()` failure**

Add to `TestFetchMessage` class in `tests/test_imap_client.py`:

```python
    @patch("email_archiver.imap_client.imaplib.IMAP4_SSL")
    def test_fetch_message_failure_returns_none(self, mock_ssl):
        """fetch_message returns None when FETCH fails."""
        mock_conn = MagicMock()
        mock_conn.uid.return_value = ("NO", [b"FETCH failed"])
        mock_ssl.return_value = mock_conn

        client = IMAPClient("imap.test.com", 993, "user", "pass")
        client.connect()
        msg = client.fetch_message(b"9999")

        self.assertIsNone(msg)

    @patch("email_archiver.imap_client.imaplib.IMAP4_SSL")
    def test_fetch_message_exception_returns_none(self, mock_ssl):
        """fetch_message returns None when FETCH raises an exception."""
        mock_conn = MagicMock()
        mock_conn.uid.side_effect = Exception("Connection lost")
        mock_ssl.return_value = mock_conn

        client = IMAPClient("imap.test.com", 993, "user", "pass")
        client.connect()
        msg = client.fetch_message(b"9999")

        self.assertIsNone(msg)
```

- [ ] **Step 4: Implement `fetch_message()` in `imap_client.py`**

Add to the import block at the top of `email_archiver/imap_client.py`, after the existing imports:

```python
import email
```

Add this method to the `IMAPClient` class, after `fetch_headers()`:

```python
    def fetch_message(self, uid: bytes) -> Optional["email.message.Message"]:
        """Fetch the complete message (headers + body + attachments).

        Uses BODY.PEEK[] to avoid marking the message as \\Seen.
        Returns a parsed email.message.Message, or None on failure.
        """
        assert self._conn is not None, "Not connected"
        try:
            typ, fetch_data = self._conn.uid("FETCH", uid, "(BODY.PEEK[])")
            if typ != "OK":
                logger.error("UID FETCH failed for %s: %s", uid.decode(), fetch_data)
                return None

            for item in fetch_data:
                if isinstance(item, tuple) and len(item) >= 2:
                    raw_bytes = item[1]
                    if isinstance(raw_bytes, bytes):
                        return email.message_from_bytes(raw_bytes)

            logger.error("No message body found in FETCH response for UID %s", uid.decode())
            return None
        except Exception as e:
            logger.error("FETCH exception for UID %s: %s", uid.decode(), e)
            return None
```

- [ ] **Step 5: Run all tests to verify they pass**

Run: `/opt/homebrew/bin/python3.13 -m unittest discover -s tests -v`

Expected: All tests pass, including the 3 new `TestFetchMessage` tests.

- [ ] **Step 6: Commit**

```bash
git add email_archiver/imap_client.py tests/test_imap_client.py
git commit -m "feat: add fetch_message() to IMAPClient for full message retrieval"
```

---

### Task 2: Invoice classification patterns and provider resolution

**Files:**
- Create: `email_archiver/invoice_scanner.py` (partial — patterns + classification functions only)
- Create: `tests/test_invoice_scanner.py` (partial — classification tests only)

- [ ] **Step 1: Write failing tests for `is_invoice()`**

Create `tests/test_invoice_scanner.py`:

```python
"""Tests for invoice scanner — classification, provider resolution, report building."""

import unittest

from email_archiver.invoice_scanner import is_invoice, resolve_provider


class TestIsInvoice(unittest.TestCase):
    """Test invoice detection patterns."""

    # --- From-address matches ---

    def test_anthropic_billing(self):
        self.assertTrue(is_invoice("billing@anthropic.com", "Your March invoice"))

    def test_xplore_billing(self):
        self.assertTrue(is_invoice("billing@xplore.ca", "Your bill is ready"))

    def test_google_payments(self):
        self.assertTrue(is_invoice("payments-noreply@google.com", "Google Workspace"))

    def test_greengeeks(self):
        self.assertTrue(is_invoice("billing@greengeeks.com", "Hosting renewal"))

    def test_telus(self):
        self.assertTrue(is_invoice("factures@telus.com", "Votre facture"))

    def test_staples(self):
        self.assertTrue(is_invoice("orders@staples.ca", "Order confirmation"))

    def test_aquavoice(self):
        self.assertTrue(is_invoice("billing@aquavoice.com", "Payment receipt"))

    def test_fal_ai(self):
        self.assertTrue(is_invoice("billing@fal.ai", "Monthly usage"))

    # --- Subject matches ---

    def test_subject_invoice(self):
        self.assertTrue(is_invoice("unknown@company.com", "Your invoice for March"))

    def test_subject_facture(self):
        self.assertTrue(is_invoice("unknown@company.com", "Votre facture mensuelle"))

    def test_subject_receipt(self):
        self.assertTrue(is_invoice("unknown@company.com", "Your receipt #12345"))

    def test_subject_recu(self):
        self.assertTrue(is_invoice("unknown@company.com", "Reçu de paiement"))

    def test_subject_billing(self):
        self.assertTrue(is_invoice("unknown@company.com", "Billing statement"))

    def test_subject_payment(self):
        self.assertTrue(is_invoice("unknown@company.com", "Payment confirmation"))

    def test_subject_your_bill(self):
        self.assertTrue(is_invoice("unknown@company.com", "Your bill is ready"))

    def test_subject_releve(self):
        self.assertTrue(is_invoice("unknown@company.com", "Votre relevé de compte"))

    def test_subject_statement(self):
        self.assertTrue(is_invoice("unknown@company.com", "Monthly statement"))

    def test_subject_order_confirmation(self):
        self.assertTrue(is_invoice("unknown@company.com", "Order confirmation #789"))

    # --- Non-matches (safe default: keep) ---

    def test_personal_email_not_invoice(self):
        self.assertFalse(is_invoice("friend@gmail.com", "Dinner tonight?"))

    def test_newsletter_not_invoice(self):
        self.assertFalse(is_invoice("news@techblog.com", "This week in tech"))

    def test_empty_not_invoice(self):
        self.assertFalse(is_invoice("", ""))

    def test_promo_not_invoice(self):
        self.assertFalse(is_invoice("deals@shop.com", "Save 50% today"))


class TestResolveProvider(unittest.TestCase):
    """Test provider name resolution from email addresses."""

    def test_known_provider_anthropic(self):
        self.assertEqual(resolve_provider("billing@anthropic.com"), "Anthropic")

    def test_known_provider_google(self):
        self.assertEqual(resolve_provider("payments-noreply@google.com"), "Google")

    def test_known_provider_xplore(self):
        self.assertEqual(resolve_provider("billing@xplore.ca"), "Xplore")

    def test_known_provider_staples(self):
        self.assertEqual(resolve_provider("orders@staples.ca"), "BureauEnGros")

    def test_known_provider_greengeeks(self):
        self.assertEqual(resolve_provider("billing@greengeeks.com"), "GreenGeeks")

    def test_known_provider_telus(self):
        self.assertEqual(resolve_provider("factures@telus.com"), "Telus")

    def test_known_provider_aquavoice(self):
        self.assertEqual(resolve_provider("billing@aquavoice.com"), "AquaVoice")

    def test_known_provider_fal(self):
        self.assertEqual(resolve_provider("billing@fal.ai"), "Fal")

    def test_unknown_provider_derives_from_domain(self):
        self.assertEqual(resolve_provider("billing@newservice.io"), "Newservice")

    def test_unknown_provider_complex_domain(self):
        self.assertEqual(resolve_provider("noreply@mail.bigcorp.com"), "Bigcorp")

    def test_unknown_provider_subdomain(self):
        self.assertEqual(resolve_provider("billing@e.company.org"), "Company")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/opt/homebrew/bin/python3.13 -m unittest tests.test_invoice_scanner -v`

Expected: `ModuleNotFoundError: No module named 'email_archiver.invoice_scanner'`

- [ ] **Step 3: Implement classification functions in `invoice_scanner.py`**

Create `email_archiver/invoice_scanner.py`:

```python
"""
Invoice scanner: identify invoices/subscriptions in Gmail inbox.

Two-pass scan:
  Pass 1 — fetch headers (lightweight) for all UIDs, classify by patterns
  Pass 2 — fetch full messages (heavy) only for matches, check for PDF attachments

Read-only: no COPY, no DELETE, no EXPUNGE, no flag changes.
"""

import csv
import email
import email.utils
import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from email_archiver.config import get_password, get_provider
from email_archiver.imap_client import IMAPClient
from email_archiver.logging_setup import setup_logging

logger = logging.getLogger("email_archiver")

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"

# ---------------------------------------------------------------------------
# Invoice detection patterns (separate from classifier.py)
# ---------------------------------------------------------------------------

# From-address substrings that indicate invoice/billing senders
INVOICE_FROM_PATTERNS: List[str] = [
    "anthropic",
    "xplore.ca",
    "staples.ca",
    "greengeeks",
    "aquavoice",
    "fal.ai",
    "telus",
    "google.com",
    "hydro",
    "desjardins",
    "interac.ca",
    "paypal",
]

# Subject regexes that indicate an invoice/receipt/billing email
INVOICE_SUBJECT_STRINGS: List[str] = [
    r"invoice",
    r"facture",
    r"receipt",
    r"re[cç]u",
    r"billing",
    r"payment",
    r"your bill",
    r"relev[eé]",
    r"statement",
    r"order confirmation",
]

_INVOICE_SUBJECT_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in INVOICE_SUBJECT_STRINGS
]

# Provider name normalization: from-address substring -> display name
PROVIDER_MAP: Dict[str, str] = {
    "anthropic": "Anthropic",
    "google.com": "Google",
    "xplore.ca": "Xplore",
    "staples": "BureauEnGros",
    "greengeeks": "GreenGeeks",
    "telus": "Telus",
    "aquavoice": "AquaVoice",
    "fal.ai": "Fal",
    "hydro": "Hydro-Quebec",
    "desjardins": "Desjardins",
    "interac.ca": "Interac",
    "paypal": "PayPal",
}


def is_invoice(from_addr: str, subject: str) -> bool:
    """Returns True if the email looks like an invoice/receipt/billing email.

    Matches on from-address substrings OR subject regexes.
    Safe default: returns False if no pattern matches.
    """
    if not from_addr and not subject:
        return False

    from_lower = from_addr.lower()
    for pattern in INVOICE_FROM_PATTERNS:
        if pattern in from_lower:
            return True

    for pattern in _INVOICE_SUBJECT_PATTERNS:
        if pattern.search(subject):
            return True

    return False


def resolve_provider(from_addr: str) -> str:
    """Resolve a from-address to a normalized provider name.

    Known providers get their display name from PROVIDER_MAP.
    Unknown providers get a capitalized name derived from the email domain.
    """
    from_lower = from_addr.lower()

    for substring, display_name in PROVIDER_MAP.items():
        if substring in from_lower:
            return display_name

    # Unknown provider: derive from domain
    # Extract domain from email address
    match = re.search(r"@([a-zA-Z0-9.-]+)", from_addr)
    if not match:
        return "Unknown"

    domain = match.group(1).lower()
    # Remove common prefixes (mail., e., email., etc.)
    parts = domain.split(".")
    # Find the meaningful part: skip subdomains, use second-to-last part
    # e.g., "mail.bigcorp.com" -> "Bigcorp", "e.company.org" -> "Company"
    if len(parts) >= 3:
        name = parts[-2]
    elif len(parts) >= 2:
        name = parts[-2]
    else:
        name = parts[0]

    return name.capitalize()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/opt/homebrew/bin/python3.13 -m unittest tests.test_invoice_scanner -v`

Expected: All 27 tests pass.

- [ ] **Step 5: Commit**

```bash
git add email_archiver/invoice_scanner.py tests/test_invoice_scanner.py
git commit -m "feat: add invoice classification patterns and provider resolution"
```

---

### Task 3: Invoice scanner — two-pass scan and report generation

**Files:**
- Modify: `email_archiver/invoice_scanner.py` (add `_extract_pdf_info()`, `_build_report()`, `_write_reports()`, `run_scan()`)
- Modify: `tests/test_invoice_scanner.py` (add tests for PDF info extraction and report building)

- [ ] **Step 1: Write failing tests for `_extract_pdf_info()`**

Add to `tests/test_invoice_scanner.py`:

```python
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

from email_archiver.invoice_scanner import extract_pdf_info


class TestExtractPdfInfo(unittest.TestCase):
    """Test PDF attachment detection from email.message.Message objects."""

    def _make_email_with_pdf(self, filename="invoice.pdf", pdf_content=b"%PDF-1.4 fake"):
        """Helper: create a MIME email with a PDF attachment."""
        msg = MIMEMultipart()
        msg["From"] = "billing@anthropic.com"
        msg["Subject"] = "Your invoice"
        msg["Date"] = "Thu, 01 Apr 2026 10:00:00 +0000"

        body = MIMEText("Please find your invoice attached.", "plain")
        msg.attach(body)

        pdf = MIMEBase("application", "pdf")
        pdf.set_payload(pdf_content)
        encoders.encode_base64(pdf)
        pdf.add_header("Content-Disposition", "attachment", filename=filename)
        msg.attach(pdf)

        return msg

    def _make_email_no_attachment(self):
        """Helper: create a plain text email with no attachments."""
        msg = MIMEText("Your invoice is available at https://billing.example.com/inv/123")
        msg["From"] = "billing@example.com"
        msg["Subject"] = "Your invoice is ready"
        msg["Date"] = "Thu, 01 Apr 2026 10:00:00 +0000"
        return msg

    def test_email_with_pdf_detected(self):
        msg = self._make_email_with_pdf("invoice-march.pdf", b"%PDF" + b"\x00" * 100)
        info = extract_pdf_info(msg)
        self.assertTrue(info["has_pdf"])
        self.assertEqual(len(info["pdf_files"]), 1)
        self.assertEqual(info["pdf_files"][0]["filename"], "invoice-march.pdf")
        self.assertGreater(info["pdf_files"][0]["size_bytes"], 0)

    def test_email_without_pdf(self):
        msg = self._make_email_no_attachment()
        info = extract_pdf_info(msg)
        self.assertFalse(info["has_pdf"])
        self.assertEqual(len(info["pdf_files"]), 0)

    def test_email_with_multiple_pdfs(self):
        msg = MIMEMultipart()
        msg["From"] = "billing@company.com"
        msg["Subject"] = "Monthly invoices"
        msg["Date"] = "Thu, 01 Apr 2026 10:00:00 +0000"
        msg.attach(MIMEText("Two invoices attached."))

        for name in ["invoice-1.pdf", "invoice-2.pdf"]:
            pdf = MIMEBase("application", "pdf")
            pdf.set_payload(b"%PDF-fake-content")
            encoders.encode_base64(pdf)
            pdf.add_header("Content-Disposition", "attachment", filename=name)
            msg.attach(pdf)

        info = extract_pdf_info(msg)
        self.assertTrue(info["has_pdf"])
        self.assertEqual(len(info["pdf_files"]), 2)
        filenames = [f["filename"] for f in info["pdf_files"]]
        self.assertIn("invoice-1.pdf", filenames)
        self.assertIn("invoice-2.pdf", filenames)

    def test_link_only_detected(self):
        html_body = '<html><body><a href="https://billing.example.com/invoice/123">View invoice</a></body></html>'
        msg = MIMEText(html_body, "html")
        msg["From"] = "billing@example.com"
        msg["Subject"] = "Your invoice"
        msg["Date"] = "Thu, 01 Apr 2026 10:00:00 +0000"
        info = extract_pdf_info(msg)
        self.assertFalse(info["has_pdf"])
        self.assertTrue(info["link_only"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/opt/homebrew/bin/python3.13 -m unittest tests.test_invoice_scanner.TestExtractPdfInfo -v`

Expected: `ImportError: cannot import name 'extract_pdf_info'`

- [ ] **Step 3: Write failing tests for `build_report()`**

Add to `tests/test_invoice_scanner.py`:

```python
from email_archiver.invoice_scanner import build_report


class TestBuildReport(unittest.TestCase):
    """Test report generation from invoice scan data."""

    def test_report_structure(self):
        invoices = [
            {
                "uid": "4532",
                "from": "billing@anthropic.com",
                "provider": "Anthropic",
                "subject": "Your March invoice",
                "date": "2026-03-01",
                "has_pdf": True,
                "link_only": False,
                "pdf_files": [{"filename": "invoice.pdf", "size_bytes": 45230}],
            },
            {
                "uid": "4600",
                "from": "billing@anthropic.com",
                "provider": "Anthropic",
                "subject": "Your April invoice",
                "date": "2026-04-01",
                "has_pdf": True,
                "link_only": False,
                "pdf_files": [{"filename": "invoice.pdf", "size_bytes": 42100}],
            },
            {
                "uid": "5000",
                "from": "payments@google.com",
                "provider": "Google",
                "subject": "Google Workspace invoice",
                "date": "2026-03-15",
                "has_pdf": False,
                "link_only": True,
                "pdf_files": [],
            },
        ]

        report = build_report("gmail", invoices, total_scanned=1200)

        self.assertEqual(report["account"], "gmail")
        self.assertEqual(report["total_emails_scanned"], 1200)
        self.assertEqual(report["invoices_found"], 3)

        # Provider summary
        self.assertIn("Anthropic", report["providers"])
        self.assertEqual(report["providers"]["Anthropic"]["count"], 2)
        self.assertTrue(report["providers"]["Anthropic"]["has_pdf_attachments"])
        self.assertIn("2026-03", report["providers"]["Anthropic"]["months"])
        self.assertIn("2026-04", report["providers"]["Anthropic"]["months"])

        self.assertIn("Google", report["providers"])
        self.assertEqual(report["providers"]["Google"]["count"], 1)
        self.assertFalse(report["providers"]["Google"]["has_pdf_attachments"])
        self.assertTrue(report["providers"]["Google"]["link_only"])

        # Invoice list
        self.assertEqual(len(report["invoices"]), 3)

    def test_report_empty_invoices(self):
        report = build_report("gmail", [], total_scanned=500)
        self.assertEqual(report["invoices_found"], 0)
        self.assertEqual(report["providers"], {})
        self.assertEqual(report["invoices"], [])
```

- [ ] **Step 4: Implement `extract_pdf_info()` and `build_report()`**

Add these functions to `email_archiver/invoice_scanner.py`, after `resolve_provider()`:

```python
def extract_pdf_info(msg: email.message.Message) -> Dict[str, Any]:
    """Extract PDF attachment info from a parsed email message.

    Returns a dict with:
      - has_pdf: bool
      - link_only: bool (True if no PDF but HTML body contains a link)
      - pdf_files: list of {filename, size_bytes}
    """
    pdf_files: List[Dict[str, Any]] = []

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            filename = part.get_filename()

            is_pdf = (
                content_type == "application/pdf"
                or (filename and filename.lower().endswith(".pdf"))
            )
            if is_pdf and filename:
                payload = part.get_payload(decode=True)
                size = len(payload) if payload else 0
                pdf_files.append({"filename": filename, "size_bytes": size})

    if pdf_files:
        return {"has_pdf": True, "link_only": False, "pdf_files": pdf_files}

    # Check for invoice links in HTML body
    link_only = False
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                html = part.get_payload(decode=True)
                if html and re.search(rb"https?://[^\s\"']+invoice", html, re.IGNORECASE):
                    link_only = True
                    break
    else:
        content_type = msg.get_content_type()
        if content_type == "text/html":
            html = msg.get_payload(decode=True)
            if html and re.search(rb"https?://[^\s\"']+invoice", html, re.IGNORECASE):
                link_only = True

    return {"has_pdf": False, "link_only": link_only, "pdf_files": []}


def build_report(
    account: str,
    invoices: List[Dict[str, Any]],
    total_scanned: int,
) -> Dict[str, Any]:
    """Build the structured scan report from invoice data.

    Returns the full report dict ready for JSON serialization.
    """
    providers: Dict[str, Dict[str, Any]] = {}

    for inv in invoices:
        prov = inv["provider"]
        if prov not in providers:
            providers[prov] = {
                "count": 0,
                "has_pdf_attachments": False,
                "link_only": False,
                "months": [],
            }

        providers[prov]["count"] += 1

        if inv["has_pdf"]:
            providers[prov]["has_pdf_attachments"] = True
        if inv["link_only"]:
            providers[prov]["link_only"] = True

        # Extract month from date (YYYY-MM)
        if inv.get("date"):
            month = inv["date"][:7]
            if month not in providers[prov]["months"]:
                providers[prov]["months"].append(month)

    # Sort months within each provider
    for prov_data in providers.values():
        prov_data["months"].sort()

    return {
        "scan_date": datetime.now().strftime("%Y-%m-%d"),
        "account": account,
        "total_emails_scanned": total_scanned,
        "invoices_found": len(invoices),
        "providers": providers,
        "invoices": invoices,
    }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `/opt/homebrew/bin/python3.13 -m unittest tests.test_invoice_scanner -v`

Expected: All tests pass (27 classification + 7 PDF + 2 report = 36 tests).

- [ ] **Step 6: Implement `_write_reports()` and `run_scan()` in `invoice_scanner.py`**

Add these functions to `email_archiver/invoice_scanner.py`, after `build_report()`:

```python
def _write_reports(report: Dict[str, Any], account: str) -> Tuple[Path, Path]:
    """Write scan report to JSON and TXT files.

    Uses atomic write (tmp + rename) for the JSON file.
    Returns (json_path, txt_path).
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # JSON report — atomic write
    json_path = REPORTS_DIR / f"{account}-invoices-scan.json"
    tmp_path = json_path.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    tmp_path.rename(json_path)

    # TXT report — human-readable summary
    txt_path = REPORTS_DIR / f"{account}-invoices-scan.txt"
    lines = [
        f"=== Scan des factures — {account.upper()} ===",
        f"Date du scan : {report['scan_date']}",
        f"Courriels scannés : {report['total_emails_scanned']}",
        f"Factures trouvées : {report['invoices_found']}",
        "",
        "ABONNEMENTS IDENTIFIÉS :",
    ]

    for prov_name in sorted(report["providers"].keys()):
        prov = report["providers"][prov_name]
        count = prov["count"]
        if prov["has_pdf_attachments"]:
            tag = "[PDF]"
        elif prov.get("link_only"):
            tag = "[LIEN]"
        else:
            tag = "[?]"
        lines.append(f"  {prov_name:<20s} {count} factures  {tag}")

    # Section for link-only providers
    link_only_provs = [
        name for name, data in report["providers"].items()
        if not data["has_pdf_attachments"] and data.get("link_only")
    ]
    if link_only_provs:
        lines.append("")
        lines.append("SANS PDF (à télécharger manuellement) :")
        for name in sorted(link_only_provs):
            lines.append(f"  {name} — liens dans les courriels")

    lines.append("")

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return json_path, txt_path


def run_scan(account: str) -> Dict[str, Any]:
    """Run the two-pass invoice scan (read-only).

    Pass 1: fetch headers for all UIDs, classify by patterns.
    Pass 2: fetch full messages for matches only, check for PDF attachments.

    Returns the scan report dict.
    """
    log = setup_logging(account)
    provider = get_provider(account)
    batch_size = provider["batch_size"]
    max_errors = provider["max_consecutive_errors"]

    log.info("=== INVOICE SCAN START === account=%s", account)
    start_time = time.time()

    password = get_password(provider["keychain_service"])
    client = IMAPClient(
        host=provider["host"],
        port=provider["port"],
        login=provider["login"],
        password=password,
    )

    invoices: List[Dict[str, Any]] = []
    consecutive_errors = 0
    total_scanned = 0

    try:
        client.connect()
        client.select_folder(provider["source_folder"])
        all_uids = client.search_all_uids()
        total_scanned = len(all_uids)

        # --- Pass 1: headers only (lightweight) ---
        log.info("Pass 1: Fetching headers for %d emails...", total_scanned)
        invoice_uids: List[Tuple[bytes, str, str]] = []  # (uid, from_addr, subject)

        for i in range(0, len(all_uids), batch_size):
            batch = all_uids[i : i + batch_size]
            try:
                headers = client.fetch_headers(batch)
                consecutive_errors = 0
            except Exception as e:
                consecutive_errors += 1
                log.error("FETCH headers error batch %d: %s", i, e)
                if consecutive_errors >= max_errors:
                    log.error(
                        "CIRCUIT BREAKER: %d consecutive errors. STOPPING.",
                        consecutive_errors,
                    )
                    break
                continue

            for uid, from_addr, subject in headers:
                if is_invoice(from_addr, subject):
                    invoice_uids.append((uid, from_addr, subject))

            if (i + len(batch)) % 500 == 0 or (i + len(batch)) >= len(all_uids):
                log.info(
                    "  Pass 1: %d/%d scanned, %d invoices found so far",
                    i + len(batch), len(all_uids), len(invoice_uids),
                )

        log.info(
            "Pass 1 done: %d invoice candidates out of %d emails.",
            len(invoice_uids), total_scanned,
        )

        # --- Pass 2: full messages for invoice candidates only ---
        log.info("Pass 2: Fetching full messages for %d candidates...", len(invoice_uids))
        consecutive_errors = 0
        scan_batch_size = 25  # Smaller batches for full messages

        for i in range(0, len(invoice_uids), scan_batch_size):
            batch = invoice_uids[i : i + scan_batch_size]

            for uid, from_addr, subject in batch:
                msg = client.fetch_message(uid)
                if msg is None:
                    consecutive_errors += 1
                    if consecutive_errors >= max_errors:
                        log.error(
                            "CIRCUIT BREAKER: %d consecutive FETCH errors. STOPPING.",
                            consecutive_errors,
                        )
                        break
                    continue

                consecutive_errors = 0

                # Extract date from email headers
                date_str = ""
                date_header = msg.get("Date", "")
                if date_header:
                    try:
                        dt = email.utils.parsedate_to_datetime(date_header)
                        date_str = dt.strftime("%Y-%m-%d")
                    except Exception:
                        date_str = ""

                provider_name = resolve_provider(from_addr)
                pdf_info = extract_pdf_info(msg)

                invoice_record: Dict[str, Any] = {
                    "uid": uid.decode() if isinstance(uid, bytes) else str(uid),
                    "from": from_addr,
                    "provider": provider_name,
                    "subject": subject,
                    "date": date_str,
                    "has_pdf": pdf_info["has_pdf"],
                    "link_only": pdf_info["link_only"],
                    "pdf_files": pdf_info["pdf_files"],
                }

                invoices.append(invoice_record)
                log.info(
                    "[INVOICE] %s | %s | %s | PDF=%s",
                    provider_name, from_addr, subject[:50],
                    "yes" if pdf_info["has_pdf"] else "no",
                )

            # Check if circuit breaker tripped inside inner loop
            if consecutive_errors >= max_errors:
                break

    except Exception as e:
        log.error("Unexpected error during scan: %s", e)
    finally:
        client.disconnect()

    duration = round(time.time() - start_time, 1)

    # Build and write reports
    report = build_report(account, invoices, total_scanned)
    json_path, txt_path = _write_reports(report, account)

    log.info("Reports written: %s, %s", json_path, txt_path)
    log.info(
        "=== INVOICE SCAN END === invoices=%d scanned=%d duration=%ss",
        len(invoices), total_scanned, duration,
    )

    # Print summary to stdout
    print(f"\n{'=' * 50}")
    print(f"  {account.upper()} — Scan des factures terminé")
    print(f"{'=' * 50}")
    print(f"  Courriels scannés : {total_scanned}")
    print(f"  Factures trouvées : {len(invoices)}")
    print()
    for prov_name in sorted(report["providers"].keys()):
        prov = report["providers"][prov_name]
        tag = "[PDF]" if prov["has_pdf_attachments"] else "[LIEN]" if prov.get("link_only") else "[?]"
        print(f"  {prov_name:<20s} {prov['count']} factures  {tag}")
    print(f"\n  Rapports : {json_path}")
    print(f"             {txt_path}")
    print(f"  Durée : {duration}s")

    return report
```

- [ ] **Step 7: Run all tests to verify nothing broke**

Run: `/opt/homebrew/bin/python3.13 -m unittest discover -s tests -v`

Expected: All tests pass.

- [ ] **Step 8: Commit**

```bash
git add email_archiver/invoice_scanner.py tests/test_invoice_scanner.py
git commit -m "feat: add invoice scanner with two-pass scan and report generation"
```

---

### Task 4: Invoice downloader — PDF extraction, file naming, CSV generation

**Files:**
- Create: `email_archiver/invoice_downloader.py`
- Create: `tests/test_invoice_downloader.py`

- [ ] **Step 1: Write failing tests for `make_pdf_filename()`**

Create `tests/test_invoice_downloader.py`:

```python
"""Tests for invoice downloader — PDF extraction, naming, CSV generation."""

import csv
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

from email_archiver.invoice_downloader import make_pdf_filename, extract_and_save_pdfs, write_csv


class TestMakePdfFilename(unittest.TestCase):
    """Test PDF filename generation."""

    def test_normal_filename(self):
        result = make_pdf_filename("2026-04-01", "invoice-march.pdf", "Anthropic")
        self.assertEqual(result, "2026-04-01-invoice-march.pdf")

    def test_generic_filename_gets_provider_prefix(self):
        result = make_pdf_filename("2026-04-01", "invoice.pdf", "Anthropic")
        self.assertEqual(result, "2026-04-01-anthropic-invoice.pdf")

    def test_generic_document_pdf(self):
        result = make_pdf_filename("2026-04-01", "document.pdf", "Google")
        self.assertEqual(result, "2026-04-01-google-document.pdf")

    def test_no_date(self):
        result = make_pdf_filename("", "invoice-123.pdf", "Anthropic")
        self.assertEqual(result, "invoice-123.pdf")

    def test_filename_already_has_provider(self):
        """If filename already contains provider-like info, just prepend date."""
        result = make_pdf_filename("2026-04-01", "anthropic-invoice-march.pdf", "Anthropic")
        self.assertEqual(result, "2026-04-01-anthropic-invoice-march.pdf")


class TestExtractAndSavePdfs(unittest.TestCase):
    """Test PDF extraction and saving from email messages."""

    def _make_email_with_pdf(self, filename="invoice.pdf", content=b"%PDF-fake"):
        msg = MIMEMultipart()
        msg["From"] = "billing@anthropic.com"
        msg["Subject"] = "Your invoice"
        msg["Date"] = "Wed, 01 Apr 2026 10:00:00 +0000"
        msg.attach(MIMEText("Invoice attached."))

        pdf = MIMEBase("application", "pdf")
        pdf.set_payload(content)
        encoders.encode_base64(pdf)
        pdf.add_header("Content-Disposition", "attachment", filename=filename)
        msg.attach(pdf)
        return msg

    def test_extracts_pdf_to_directory(self):
        msg = self._make_email_with_pdf("invoice-march.pdf", b"%PDF-test-content")
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            saved = extract_and_save_pdfs(msg, "2026-04-01", "Anthropic", output_dir)

            self.assertEqual(len(saved), 1)
            saved_path = output_dir / saved[0]
            self.assertTrue(saved_path.exists())
            self.assertEqual(saved_path.read_bytes(), b"%PDF-test-content")

    def test_skips_existing_same_size(self):
        msg = self._make_email_with_pdf("invoice.pdf", b"%PDF-content")
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            # First extraction
            saved1 = extract_and_save_pdfs(msg, "2026-04-01", "Anthropic", output_dir)
            # Second extraction — should skip
            saved2 = extract_and_save_pdfs(msg, "2026-04-01", "Anthropic", output_dir)
            self.assertEqual(len(saved1), 1)
            self.assertEqual(len(saved2), 0)

    def test_no_attachments_returns_empty(self):
        msg = MIMEText("No attachments here.")
        msg["From"] = "billing@example.com"
        msg["Date"] = "Wed, 01 Apr 2026 10:00:00 +0000"
        with tempfile.TemporaryDirectory() as tmpdir:
            saved = extract_and_save_pdfs(msg, "2026-04-01", "Example", Path(tmpdir))
            self.assertEqual(len(saved), 0)


class TestWriteCsv(unittest.TestCase):
    """Test CSV summary generation."""

    def test_csv_output(self):
        rows = [
            {
                "date": "2026-04-01",
                "fournisseur": "Anthropic",
                "sujet": "Your March invoice",
                "fichier_pdf": "2026-04-01-invoice.pdf",
                "source_email": "billing@anthropic.com",
            },
            {
                "date": "2026-04-15",
                "fournisseur": "Telus",
                "sujet": "Votre facture",
                "fichier_pdf": "",
                "source_email": "factures@telus.com",
            },
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "recapitulatif.csv"
            write_csv(rows, csv_path)

            self.assertTrue(csv_path.exists())
            content = csv_path.read_text(encoding="utf-8-sig")
            reader = csv.DictReader(io.StringIO(content))
            result_rows = list(reader)

            self.assertEqual(len(result_rows), 2)
            self.assertEqual(result_rows[0]["fournisseur"], "Anthropic")
            self.assertEqual(result_rows[1]["fichier_pdf"], "")

    def test_csv_empty_rows(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "recapitulatif.csv"
            write_csv([], csv_path)

            self.assertTrue(csv_path.exists())
            content = csv_path.read_text(encoding="utf-8-sig")
            reader = csv.DictReader(io.StringIO(content))
            self.assertEqual(len(list(reader)), 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/opt/homebrew/bin/python3.13 -m unittest tests.test_invoice_downloader -v`

Expected: `ModuleNotFoundError: No module named 'email_archiver.invoice_downloader'`

- [ ] **Step 3: Implement `invoice_downloader.py`**

Create `email_archiver/invoice_downloader.py`:

```python
"""
Invoice downloader: extract PDF attachments and generate CSV summaries.

Reads the scan report (from invoice_scanner), connects to IMAP,
fetches only the messages for the target month, extracts PDFs,
and writes a CSV summary.

Read-only on the server: no COPY, no DELETE, no EXPUNGE, no flag changes.
"""

import csv
import email
import email.utils
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from email_archiver.config import get_password, get_provider
from email_archiver.imap_client import IMAPClient
from email_archiver.logging_setup import setup_logging

logger = logging.getLogger("email_archiver")

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"
FACTURES_DIR = Path(__file__).resolve().parent.parent / "factures"

# Generic filenames that should be prefixed with the provider name
_GENERIC_NAMES = {"invoice.pdf", "document.pdf", "facture.pdf", "receipt.pdf", "bill.pdf"}


def make_pdf_filename(date_str: str, original_name: str, provider: str) -> str:
    """Generate a descriptive PDF filename.

    Format: YYYY-MM-DD-original-name.pdf
    If original name is generic (e.g., "invoice.pdf"), prefix with provider.
    If no date, return original name as-is.
    """
    if not date_str:
        return original_name

    name_lower = original_name.lower()
    if name_lower in _GENERIC_NAMES:
        return f"{date_str}-{provider.lower()}-{original_name}"

    return f"{date_str}-{original_name}"


def extract_and_save_pdfs(
    msg: email.message.Message,
    date_str: str,
    provider: str,
    output_dir: Path,
) -> List[str]:
    """Extract PDF attachments from an email and save to output_dir.

    Returns list of saved filenames (relative to output_dir).
    Skips files that already exist with the same size.
    """
    saved: List[str] = []

    if not msg.is_multipart():
        return saved

    output_dir.mkdir(parents=True, exist_ok=True)

    for part in msg.walk():
        content_type = part.get_content_type()
        filename = part.get_filename()

        is_pdf = (
            content_type == "application/pdf"
            or (filename and filename.lower().endswith(".pdf"))
        )

        if not is_pdf or not filename:
            continue

        payload = part.get_payload(decode=True)
        if not payload:
            continue

        dest_name = make_pdf_filename(date_str, filename, provider)
        dest_path = output_dir / dest_name

        # Skip if already exists with same size
        if dest_path.exists() and dest_path.stat().st_size == len(payload):
            logger.info("[SKIP] %s (already exists, same size)", dest_name)
            continue

        dest_path.write_bytes(payload)
        saved.append(dest_name)
        logger.info("[SAVED] %s (%d bytes)", dest_name, len(payload))

    return saved


def write_csv(rows: List[Dict[str, str]], csv_path: Path) -> None:
    """Write the CSV summary file.

    Uses UTF-8 with BOM for Excel compatibility.
    """
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["date", "fournisseur", "sujet", "fichier_pdf", "source_email"]

    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def run_download(account: str, month: Optional[str] = None) -> Dict[str, Any]:
    """Download invoice PDFs for a specific month.

    Reads the scan report, connects to IMAP, fetches targeted messages,
    extracts PDFs, and generates the CSV summary.

    Args:
        account: Provider name (e.g., "gmail")
        month: Target month as "YYYY-MM". Defaults to current month.

    Returns dict with download stats.
    """
    if month is None:
        month = datetime.now().strftime("%Y-%m")

    log = setup_logging(account)

    # Load scan report
    scan_path = REPORTS_DIR / f"{account}-invoices-scan.json"
    if not scan_path.exists():
        print(
            f"\nERREUR : Aucun scan trouvé pour '{account}'.\n"
            f"Exécute d'abord : python -m email_archiver invoices scan {account}\n"
        )
        return {"downloaded": 0, "skipped": 0, "no_pdf": 0, "errors": 0}

    with open(scan_path, encoding="utf-8") as f:
        scan_data = json.load(f)

    # Filter invoices for the target month
    target_invoices = [
        inv for inv in scan_data.get("invoices", [])
        if inv.get("date", "").startswith(month)
    ]

    if not target_invoices:
        print(f"\nAucune facture trouvée pour {month} dans le scan de '{account}'.")
        return {"downloaded": 0, "skipped": 0, "no_pdf": 0, "errors": 0}

    log.info(
        "=== INVOICE DOWNLOAD START === account=%s month=%s invoices=%d",
        account, month, len(target_invoices),
    )
    start_time = time.time()

    provider = get_provider(account)
    password = get_password(provider["keychain_service"])
    client = IMAPClient(
        host=provider["host"],
        port=provider["port"],
        login=provider["login"],
        password=password,
    )

    month_dir = FACTURES_DIR / month
    downloaded = 0
    skipped = 0
    no_pdf = 0
    errors = 0
    csv_rows: List[Dict[str, str]] = []

    try:
        client.connect()
        client.select_folder(provider["source_folder"])

        for inv in target_invoices:
            uid = inv["uid"].encode() if isinstance(inv["uid"], str) else inv["uid"]
            provider_name = inv["provider"]
            provider_dir = month_dir / provider_name

            if not inv.get("has_pdf"):
                log.info("[NO-PDF] %s | %s", provider_name, inv["subject"][:50])
                no_pdf += 1
                csv_rows.append({
                    "date": inv.get("date", ""),
                    "fournisseur": provider_name,
                    "sujet": inv.get("subject", ""),
                    "fichier_pdf": "",
                    "source_email": inv.get("from", ""),
                })
                continue

            msg = client.fetch_message(uid)
            if msg is None:
                log.error("[ERROR] Failed to fetch UID %s", inv["uid"])
                errors += 1
                continue

            saved = extract_and_save_pdfs(
                msg, inv.get("date", ""), provider_name, provider_dir,
            )

            if saved:
                downloaded += len(saved)
                for filename in saved:
                    csv_rows.append({
                        "date": inv.get("date", ""),
                        "fournisseur": provider_name,
                        "sujet": inv.get("subject", ""),
                        "fichier_pdf": filename,
                        "source_email": inv.get("from", ""),
                    })
            else:
                skipped += 1
                log.info("[SKIP] %s | %s (already downloaded)", provider_name, inv["subject"][:50])

    except Exception as e:
        log.error("Unexpected error during download: %s", e)
        errors += 1
    finally:
        client.disconnect()

    # Write CSV summary
    csv_path = month_dir / "recapitulatif.csv"
    if csv_rows:
        write_csv(csv_rows, csv_path)
        log.info("CSV written: %s", csv_path)

    duration = round(time.time() - start_time, 1)
    log.info(
        "=== INVOICE DOWNLOAD END === downloaded=%d skipped=%d no_pdf=%d errors=%d duration=%ss",
        downloaded, skipped, no_pdf, errors, duration,
    )

    # Print summary
    print(f"\n{'=' * 50}")
    print(f"  {account.upper()} — Téléchargement des factures ({month})")
    print(f"{'=' * 50}")
    print(f"  PDFs téléchargés : {downloaded}")
    print(f"  Déjà téléchargés : {skipped}")
    print(f"  Sans PDF         : {no_pdf}")
    print(f"  Erreurs          : {errors}")
    if csv_rows:
        print(f"\n  CSV : {csv_path}")
    print(f"  Dossier : {month_dir}")
    print(f"  Durée : {duration}s")

    return {
        "downloaded": downloaded,
        "skipped": skipped,
        "no_pdf": no_pdf,
        "errors": errors,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/opt/homebrew/bin/python3.13 -m unittest tests.test_invoice_downloader -v`

Expected: All 8 tests pass.

- [ ] **Step 5: Run full test suite**

Run: `/opt/homebrew/bin/python3.13 -m unittest discover -s tests -v`

Expected: All tests pass (existing + new).

- [ ] **Step 6: Commit**

```bash
git add email_archiver/invoice_downloader.py tests/test_invoice_downloader.py
git commit -m "feat: add invoice downloader with PDF extraction and CSV generation"
```

---

### Task 5: CLI integration

**Files:**
- Modify: `email_archiver/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests for CLI argument parsing**

Create `tests/test_cli.py`:

```python
"""Tests for CLI argument parsing."""

import unittest
from unittest.mock import patch, MagicMock

from email_archiver.cli import main


class TestInvoicesCLI(unittest.TestCase):
    """Test the invoices subcommand argument parsing."""

    @patch("email_archiver.cli.run_scan")
    def test_invoices_scan(self, mock_scan):
        mock_scan.return_value = {"invoices_found": 5}
        with patch("sys.argv", ["email-archiver", "invoices", "scan", "gmail"]):
            main()
        mock_scan.assert_called_once_with("gmail")

    @patch("email_archiver.cli.run_download")
    def test_invoices_download_with_month(self, mock_download):
        mock_download.return_value = {"downloaded": 3}
        with patch("sys.argv", ["email-archiver", "invoices", "download", "gmail", "--month", "2026-04"]):
            main()
        mock_download.assert_called_once_with("gmail", month="2026-04")

    @patch("email_archiver.cli.run_download")
    def test_invoices_download_default_month(self, mock_download):
        mock_download.return_value = {"downloaded": 0}
        with patch("sys.argv", ["email-archiver", "invoices", "download", "gmail"]):
            main()
        mock_download.assert_called_once_with("gmail", month=None)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/opt/homebrew/bin/python3.13 -m unittest tests.test_cli -v`

Expected: Failures — `run_scan` and `run_download` not imported in cli.py, `invoices` subcommand doesn't exist.

- [ ] **Step 3: Update `cli.py` with the `invoices` subcommand**

Replace the entire contents of `email_archiver/cli.py` with:

```python
"""
CLI entry point for email-archiver.

Usage:
    python -m email_archiver archive yahoo
    python -m email_archiver archive icloud
    python -m email_archiver archive all
    python -m email_archiver preview yahoo
    python -m email_archiver stats yahoo
    python -m email_archiver organize yahoo
    python -m email_archiver invoices scan gmail
    python -m email_archiver invoices download gmail --month 2026-04
"""

import argparse
import sys

from email_archiver.archiver import run_archive, run_preview, show_stats
from email_archiver.config import PROVIDERS
from email_archiver.invoice_downloader import run_download
from email_archiver.invoice_scanner import run_scan
from email_archiver.organizer import run_organize


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="email-archiver",
        description="IMAP email archiver for Gmail, iCloud, and Yahoo",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # archive
    p_archive = subparsers.add_parser("archive", help="Archive matching emails")
    p_archive.add_argument(
        "account",
        choices=[*PROVIDERS.keys(), "all"],
        help="Account to archive (or 'all')",
    )

    # preview
    p_preview = subparsers.add_parser(
        "preview", help="Preview classification (read-only)"
    )
    p_preview.add_argument(
        "account",
        choices=list(PROVIDERS.keys()),
        help="Account to preview",
    )
    p_preview.add_argument(
        "-n", "--limit",
        type=int,
        default=100,
        help="Number of emails to preview (default: 100)",
    )

    # stats
    p_stats = subparsers.add_parser("stats", help="Show cumulative stats")
    p_stats.add_argument(
        "account",
        choices=[*PROVIDERS.keys(), "all"],
        help="Account to show stats for (or 'all')",
    )

    # organize
    p_organize = subparsers.add_parser(
        "organize", help="Organize inbox into categorized folders"
    )
    p_organize.add_argument(
        "account",
        choices=[*PROVIDERS.keys(), "all"],
        help="Account to organize (or 'all')",
    )

    # invoices
    p_invoices = subparsers.add_parser(
        "invoices", help="Scan for invoices and download PDFs"
    )
    invoices_sub = p_invoices.add_subparsers(dest="action", required=True)

    # invoices scan
    p_inv_scan = invoices_sub.add_parser(
        "scan", help="Scan inbox for invoices (read-only)"
    )
    p_inv_scan.add_argument(
        "account",
        choices=list(PROVIDERS.keys()),
        help="Account to scan",
    )

    # invoices download
    p_inv_download = invoices_sub.add_parser(
        "download", help="Download invoice PDFs for a month"
    )
    p_inv_download.add_argument(
        "account",
        choices=list(PROVIDERS.keys()),
        help="Account to download from",
    )
    p_inv_download.add_argument(
        "--month",
        type=str,
        default=None,
        help="Target month as YYYY-MM (default: current month)",
    )

    args = parser.parse_args()

    if args.command == "archive":
        accounts = list(PROVIDERS.keys()) if args.account == "all" else [args.account]
        for acct in accounts:
            stats = run_archive(acct)
            print(
                f"\n{acct}: archived={stats['archived']} "
                f"kept={stats['kept']} "
                f"errors={stats['errors']} "
                f"duration={stats['duration_s']}s"
            )

    elif args.command == "preview":
        run_preview(args.account, limit=args.limit)

    elif args.command == "organize":
        accounts = list(PROVIDERS.keys()) if args.account == "all" else [args.account]
        for acct in accounts:
            run_organize(acct)

    elif args.command == "stats":
        accounts = list(PROVIDERS.keys()) if args.account == "all" else [args.account]
        for acct in accounts:
            show_stats(acct)

    elif args.command == "invoices":
        if args.action == "scan":
            run_scan(args.account)
        elif args.action == "download":
            run_download(args.account, month=args.month)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run CLI tests to verify they pass**

Run: `/opt/homebrew/bin/python3.13 -m unittest tests.test_cli -v`

Expected: All 3 tests pass.

- [ ] **Step 5: Run full test suite**

Run: `/opt/homebrew/bin/python3.13 -m unittest discover -s tests -v`

Expected: All tests pass.

- [ ] **Step 6: Add `factures/` to `.gitignore`**

The `factures/` directory contains downloaded PDFs (potentially sensitive financial data). Add it to `.gitignore`:

Check if `.gitignore` exists and add `factures/` to it. If it doesn't exist, create it with:

```
logs/
factures/
```

- [ ] **Step 7: Commit**

```bash
git add email_archiver/cli.py tests/test_cli.py .gitignore
git commit -m "feat: add 'invoices' CLI subcommand with scan and download actions"
```

---

### Task 6: Update CLAUDE.md with new commands

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add invoice commands to CLAUDE.md**

In the `## Commands` section of `CLAUDE.md`, add after the existing commands:

```markdown
/opt/homebrew/bin/python3.13 -m email_archiver invoices scan gmail    # scan for invoices (read-only)
/opt/homebrew/bin/python3.13 -m email_archiver invoices download gmail --month 2026-04  # download PDFs
```

- [ ] **Step 2: Add invoice architecture note to CLAUDE.md**

In the `## Architecture` section, update the description to mention the new modules:

```markdown
`cli.py` → delegates to `archiver.py` (archive/preview/stats), `organizer.py` (organize), `invoice_scanner.py` (invoices scan), or `invoice_downloader.py` (invoices download). All use `IMAPClient` (imap_client.py) for a single persistent IMAP connection, `classifier.py` for pattern-based email classification, and `config.py` for provider configs + macOS Keychain credential retrieval.
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with invoice extraction commands"
```
