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
    match = re.search(r"@([a-zA-Z0-9.-]+)", from_addr)
    if not match:
        return "Unknown"

    domain = match.group(1).lower()
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
