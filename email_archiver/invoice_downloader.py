"""
Invoice downloader: extract PDF attachments and generate CSV summaries.

Reads the scan report (from invoice_scanner), connects to IMAP,
fetches only the messages for the target month, extracts PDFs,
and writes a CSV summary.

Read-only on the server: no COPY, no DELETE, no EXPUNGE, no flag changes.
"""

import csv
import email
import email.message
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
