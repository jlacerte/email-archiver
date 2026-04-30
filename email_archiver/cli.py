"""
CLI entry point for email-archiver.

Usage:
    python -m email_archiver archive yahoo
    python -m email_archiver archive icloud
    python -m email_archiver archive all
    python -m email_archiver preview yahoo
    python -m email_archiver stats yahoo
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
