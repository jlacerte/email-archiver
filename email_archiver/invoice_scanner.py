"""
Invoice scanner: find invoices in pre-classified IMAP folders.

Scans Factures/* and Financier/* folders (populated by organize).
All emails in these folders are already invoices — no classification needed.
Checks each for PDF attachments and generates reports.

Read-only: no COPY, no DELETE, no EXPUNGE, no flag changes.
"""

import csv
import email
import email.message
import email.utils
import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from email_archiver.config import get_password, get_provider
from email_archiver.imap_client import IMAPClient, _decode_header_value
from email_archiver.logging_setup import setup_logging

logger = logging.getLogger("email_archiver")

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"

# Folder prefixes to scan for invoices (populated by organize)
SCAN_FOLDER_PREFIXES: List[str] = ["Factures", "Financier"]

# Provider name normalization: from-address substring -> display name
PROVIDER_MAP: Dict[str, str] = {
    "anthropic": "Anthropic",
    "payments-noreply@google.com": "Google",
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


def resolve_provider(from_addr: str) -> str:
    """Resolve a from-address to a normalized provider name.

    Known providers get their display name from PROVIDER_MAP.
    Unknown providers get a capitalized name derived from the email domain.
    """
    from_lower = from_addr.lower()

    for substring, display_name in PROVIDER_MAP.items():
        if substring in from_lower:
            return display_name

    match = re.search(r"@([a-zA-Z0-9.-]+)", from_addr)
    if not match:
        return "Unknown"

    domain = match.group(1).lower()
    parts = domain.split(".")
    if len(parts) >= 2:
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

        if inv.get("date"):
            month = inv["date"][:7]
            if month not in providers[prov]["months"]:
                providers[prov]["months"].append(month)

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

    json_path = REPORTS_DIR / f"{account}-invoices-scan.json"
    tmp_path = json_path.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    tmp_path.rename(json_path)

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


def _provider_from_folder(folder: str) -> Optional[str]:
    """Derive provider name from a Factures/ProviderName folder path.

    Returns the provider part (e.g., "Anthropic" from "Factures/Anthropic"),
    or None if the folder doesn't match the pattern.
    """
    parts = folder.split("/")
    if len(parts) >= 2 and parts[0] in ("Factures", "Financier"):
        return parts[-1]
    return None


def _scan_folder(
    client: IMAPClient,
    folder: str,
    max_errors: int,
    log: logging.Logger,
) -> Tuple[List[Dict[str, Any]], int]:
    """Scan a pre-classified folder (Factures/*, Financier/*).

    All emails in these folders are already invoices — no classification needed.
    Provider name is derived from the folder name.

    Returns (invoices_list, total_emails_in_folder).
    """
    count = client.select_folder(folder)
    if count == 0:
        return [], 0

    all_uids = client.search_all_uids()
    total = len(all_uids)
    consecutive_errors = 0
    invoices: List[Dict[str, Any]] = []

    folder_provider = _provider_from_folder(folder)

    log.info("Scanning folder '%s': %d emails...", folder, total)

    for uid in all_uids:
        msg = client.fetch_message(uid)
        if msg is None:
            consecutive_errors += 1
            if consecutive_errors >= max_errors:
                log.error(
                    "CIRCUIT BREAKER: %d consecutive FETCH errors in '%s'. STOPPING.",
                    consecutive_errors, folder,
                )
                break
            continue

        consecutive_errors = 0

        from_addr = _decode_header_value(msg.get("From", "")).lower()
        subject = _decode_header_value(msg.get("Subject", ""))
        date_str = _extract_date(msg)
        provider_name = folder_provider or resolve_provider(from_addr)
        pdf_info = extract_pdf_info(msg)

        invoices.append({
            "uid": uid.decode() if isinstance(uid, bytes) else str(uid),
            "from": from_addr,
            "provider": provider_name,
            "subject": subject,
            "date": date_str,
            "has_pdf": pdf_info["has_pdf"],
            "link_only": pdf_info["link_only"],
            "pdf_files": pdf_info["pdf_files"],
            "folder": folder,
        })
        log.info(
            "[INVOICE] %s | %s | %s | PDF=%s | folder=%s",
            provider_name, from_addr, subject[:50],
            "yes" if pdf_info["has_pdf"] else "no", folder,
        )

    return invoices, total


def _extract_date(msg: email.message.Message) -> str:
    """Extract date from email headers as YYYY-MM-DD string."""
    date_header = msg.get("Date", "")
    if date_header:
        try:
            dt = email.utils.parsedate_to_datetime(date_header)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            pass
    return ""


def run_scan(account: str) -> Dict[str, Any]:
    """Run invoice scan across pre-classified folders (read-only).

    Discovers Factures/* and Financier/* folders (populated by organize)
    and scans each for PDF attachments.

    Returns the scan report dict.
    """
    log = setup_logging(account)
    provider = get_provider(account)
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
    total_scanned = 0
    invoice_folders: List[str] = []

    try:
        client.connect()

        # Discover invoice folders
        for prefix in SCAN_FOLDER_PREFIXES:
            found = client.list_folders(f"{prefix}/*")
            invoice_folders.extend(found)

        if invoice_folders:
            log.info(
                "Found %d invoice folders: %s",
                len(invoice_folders),
                ", ".join(invoice_folders),
            )
        else:
            log.warning(
                "No Factures/* or Financier/* folders found. "
                "Run 'organize' first to sort emails into folders."
            )

        for folder in invoice_folders:
            folder_invoices, folder_total = _scan_folder(
                client, folder, max_errors, log,
            )
            invoices.extend(folder_invoices)
            total_scanned += folder_total

    except Exception as e:
        log.error("Unexpected error during scan: %s", e)
    finally:
        client.disconnect()

    duration = round(time.time() - start_time, 1)

    report = build_report(account, invoices, total_scanned)
    json_path, txt_path = _write_reports(report, account)

    log.info("Reports written: %s, %s", json_path, txt_path)
    log.info(
        "=== INVOICE SCAN END === invoices=%d scanned=%d folders=%d duration=%ss",
        len(invoices), total_scanned, len(invoice_folders), duration,
    )

    # Print summary
    print(f"\n{'=' * 50}")
    print(f"  {account.upper()} — Scan des factures terminé")
    print(f"{'=' * 50}")
    print(f"  Courriels scannés : {total_scanned}")
    print(f"  Factures trouvées : {len(invoices)}")
    if invoice_folders:
        print(f"  Dossiers scannés  : {len(invoice_folders)} dossiers")
    else:
        print(f"  Aucun dossier Factures/Financier trouvé — exécuter 'organize' d'abord")
    print()
    for prov_name in sorted(report["providers"].keys()):
        prov = report["providers"][prov_name]
        tag = "[PDF]" if prov["has_pdf_attachments"] else "[LIEN]" if prov.get("link_only") else "[?]"
        print(f"  {prov_name:<20s} {prov['count']} factures  {tag}")
    print(f"\n  Rapports : {json_path}")
    print(f"             {txt_path}")
    print(f"  Durée : {duration}s")

    return report
