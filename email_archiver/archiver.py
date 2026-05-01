"""
Archiver: preview classification and manage stats.

run_archive() has been removed — use `organize` which handles both
folder sorting and noise archiving via the unified classify() function.
"""

import json
import logging
import time
from pathlib import Path
from typing import Dict, Any

from email_archiver.classifier import classify
from email_archiver.config import get_password, get_provider
from email_archiver.imap_client import IMAPClient
from email_archiver.logging_setup import setup_logging

STATS_DIR = Path(__file__).resolve().parent.parent / "logs"


def _load_stats(account: str) -> Dict[str, Any]:
    stats_file = STATS_DIR / f"archive-{account}-stats.json"
    if stats_file.exists():
        with open(stats_file) as f:
            return json.load(f)
    return {
        "total_archived": 0,
        "total_kept": 0,
        "total_errors": 0,
        "last_session": "never",
    }


def save_stats(account: str, session_stats: Dict[str, Any]) -> None:
    """Save session stats to disk (called by organizer after run_organize)."""
    STATS_DIR.mkdir(parents=True, exist_ok=True)
    prev = _load_stats(account)
    stats = {
        "total_archived": prev["total_archived"] + session_stats.get("archived", 0),
        "total_kept": prev["total_kept"] + session_stats.get("kept", 0),
        "total_errors": prev["total_errors"] + session_stats.get("errors", 0),
        "last_session": time.strftime("%Y-%m-%d %H:%M:%S"),
        "last_session_archived": session_stats.get("archived", 0),
        "last_session_kept": session_stats.get("kept", 0),
        "last_session_moved": session_stats.get("moved", 0),
        "last_session_errors": session_stats.get("errors", 0),
        "last_session_duration_s": session_stats.get("duration_s", 0),
    }
    stats_file = STATS_DIR / f"archive-{account}-stats.json"
    tmp_file = stats_file.with_suffix(".tmp")
    with open(tmp_file, "w") as f:
        json.dump(stats, f, indent=2)
    tmp_file.rename(stats_file)


def show_stats(account: str) -> None:
    """Print cumulative stats for an account."""
    stats = _load_stats(account)
    print(f"\n=== Stats for {account} ===")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    print()


def run_preview(account: str, limit: int = 100) -> None:
    """Preview mode: fetch up to `limit` emails, classify, print results.

    Read-only — no COPY, no DELETE, no EXPUNGE. One FETCH only.
    Shows destination folder for each email.
    """
    log = setup_logging(account)
    provider = get_provider(account)

    log.info("=== PREVIEW START === account=%s limit=%d", account, limit)

    password = get_password(provider["keychain_service"])
    client = IMAPClient(
        host=provider["host"],
        port=provider["port"],
        login=provider["login"],
        password=password,
    )

    try:
        client.connect()
        client.select_folder(provider["source_folder"])
        all_uids = client.search_all_uids()

        uids_to_fetch = all_uids[:limit]
        headers = client.fetch_headers(uids_to_fetch)

        folder_count = 0
        archive_count = 0
        keep_count = 0
        for _uid, from_addr, subject in headers:
            dest = classify(from_addr, subject)
            if dest == "_archive":
                tag = "_archive"
                archive_count += 1
            elif dest == "":
                tag = "KEEP"
                keep_count += 1
            else:
                tag = dest
                folder_count += 1
            log.info("[%s] From: %s | Subject: %s", tag, from_addr, subject[:60])

        log.info(
            "=== PREVIEW END === %d to folders, %d to archive, %d keep "
            "(of %d fetched, %d total in folder)",
            folder_count, archive_count, keep_count,
            len(headers), len(all_uids),
        )
    except Exception as e:
        log.error("Preview failed: %s", e)
        raise
    finally:
        client.disconnect()
