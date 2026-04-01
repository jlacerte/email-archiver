"""
CLI entry point for email-archiver.

Usage:
    python -m email_archiver archive yahoo
    python -m email_archiver archive icloud
    python -m email_archiver archive all
    python -m email_archiver preview yahoo
    python -m email_archiver stats yahoo
"""

import argparse
import sys

from email_archiver.archiver import run_archive, run_preview, show_stats
from email_archiver.config import PROVIDERS


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="email-archiver",
        description="IMAP email archiver for iCloud and Yahoo",
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

    elif args.command == "stats":
        accounts = list(PROVIDERS.keys()) if args.account == "all" else [args.account]
        for acct in accounts:
            show_stats(acct)


if __name__ == "__main__":
    main()
