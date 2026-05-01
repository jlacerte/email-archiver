"""
CLI entry point for email-archiver.

Usage:
    python -m email_archiver organize gmail
    python -m email_archiver organize all
    python -m email_archiver preview gmail
    python -m email_archiver preview yahoo -n 20
    python -m email_archiver stats gmail
    python -m email_archiver invoices scan gmail
    python -m email_archiver invoices download gmail --month 2026-04
"""

import argparse
import sys

from email_archiver.archiver import run_preview, show_stats
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

    # organize
    p_organize = subparsers.add_parser(
        "organize", help="Sort inbox into folders + archive noise"
    )
    p_organize.add_argument(
        "account",
        choices=[*PROVIDERS.keys(), "all"],
        help="Account to organize (or 'all')",
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

    # invoices
    p_invoices = subparsers.add_parser(
        "invoices", help="Scan for invoices and download PDFs"
    )
    invoices_sub = p_invoices.add_subparsers(dest="action", required=True)

    # invoices scan
    p_inv_scan = invoices_sub.add_parser(
        "scan", help="Scan invoice folders (read-only)"
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

    if args.command == "organize":
        accounts = list(PROVIDERS.keys()) if args.account == "all" else [args.account]
        for acct in accounts:
            run_organize(acct)

    elif args.command == "preview":
        run_preview(args.account, limit=args.limit)

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
