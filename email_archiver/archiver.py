"""
Archiver orchestration: connect → scan → classify → archive → expunge.

Safety invariant: every COPY is verified (return == 'OK') before marking
\\Deleted. If any COPY fails, we STOP immediately — no deletions without
confirmed copies. Already-confirmed copies are flushed before stopping.

Circuit breaker: 3 consecutive FETCH errors → stop entirely.
"""

import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional

from email_archiver.classifier import should_archive
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


def _save_stats(account: str, session_stats: Dict[str, Any]) -> None:
    STATS_DIR.mkdir(parents=True, exist_ok=True)
    prev = _load_stats(account)
    stats = {
        "total_archived": prev["total_archived"] + session_stats["archived"],
        "total_kept": prev["total_kept"] + session_stats["kept"],
        "total_errors": prev["total_errors"] + session_stats["errors"],
        "last_session": time.strftime("%Y-%m-%d %H:%M:%S"),
        "last_session_archived": session_stats["archived"],
        "last_session_kept": session_stats["kept"],
        "last_session_errors": session_stats["errors"],
        "last_session_duration_s": session_stats["duration_s"],
    }
    stats_file = STATS_DIR / f"archive-{account}-stats.json"
    # Atomic write: write to tmp, then rename
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

        # Only fetch up to `limit`
        uids_to_fetch = all_uids[:limit]
        headers = client.fetch_headers(uids_to_fetch)

        archive_count = 0
        keep_count = 0
        for _uid, from_addr, subject in headers:
            action = "ARCHIVE" if should_archive(from_addr, subject) else "KEEP"
            if action == "ARCHIVE":
                archive_count += 1
            else:
                keep_count += 1
            log.info("[%s] From: %s | Subject: %s", action, from_addr, subject[:60])

        log.info(
            "=== PREVIEW END === %d would archive, %d would keep (of %d fetched, %d total in folder)",
            archive_count, keep_count, len(headers), len(all_uids),
        )
    except Exception as e:
        log.error("Preview failed: %s", e)
        raise
    finally:
        client.disconnect()


def run_archive(account: str) -> Dict[str, Any]:
    """Archive emails for an account.

    Returns session stats dict with archived/kept/errors/duration_s.
    """
    log = setup_logging(account)
    provider = get_provider(account)
    batch_size = provider["batch_size"]
    max_errors = provider["max_consecutive_errors"]
    archive_folder = provider["archive_folder"]

    log.info("=== SESSION START === account=%s host=%s", account, provider["host"])
    start_time = time.time()

    password = get_password(provider["keychain_service"])
    client = IMAPClient(
        host=provider["host"],
        port=provider["port"],
        login=provider["login"],
        password=password,
    )

    archived = 0
    kept = 0
    errors = 0
    consecutive_errors = 0

    try:
        client.connect()
        client.select_folder(provider["source_folder"])
        all_uids = client.search_all_uids()

        for i in range(0, len(all_uids), batch_size):
            batch = all_uids[i : i + batch_size]
            batch_to_delete = []

            # FETCH headers
            try:
                headers = client.fetch_headers(batch)
                consecutive_errors = 0
            except Exception as e:
                errors += 1
                consecutive_errors += 1
                log.error("FETCH error for batch %d-%d: %s", i, i + len(batch), e)
                if consecutive_errors >= max_errors:
                    log.error(
                        "CIRCUIT BREAKER: %d consecutive errors. STOPPING.",
                        consecutive_errors,
                    )
                    break
                continue

            # Classify and archive
            for uid, from_addr, subject in headers:
                if should_archive(from_addr, subject):
                    # COPY to Archive — VERIFY before any deletion
                    if client.archive_uid(uid, archive_folder):
                        batch_to_delete.append(uid)
                        archived += 1
                    else:
                        log.error(
                            "COPY FAILED for UID %s (%s: %s). STOPPING IMMEDIATELY.",
                            uid.decode(), from_addr, subject[:40],
                        )
                        log.error("No deletions without confirmed copies.")
                        # Flush already-confirmed copies before stopping
                        if batch_to_delete:
                            client.mark_deleted(batch_to_delete)
                            client.expunge()
                            log.info(
                                "Flushed %d confirmed copies before stopping.",
                                len(batch_to_delete),
                            )
                        raise RuntimeError(f"COPY failed for UID {uid.decode()}")
                else:
                    kept += 1

            # Flush batch: delete from source (already safely copied)
            if batch_to_delete:
                client.mark_deleted(batch_to_delete)
                client.expunge()

            # Progress
            processed = i + len(batch)
            if processed % 200 == 0 or processed >= len(all_uids):
                log.info(
                    "Progress: %d/%d scanned, +%d archived, %d kept, %d errors",
                    processed, len(all_uids), archived, kept, errors,
                )

    except RuntimeError:
        # COPY failure — already logged, stats will reflect partial run
        pass
    except Exception as e:
        log.error("Unexpected error: %s", e)
        errors += 1
    finally:
        client.disconnect()

    duration_s = round(time.time() - start_time, 1)
    session_stats = {
        "archived": archived,
        "kept": kept,
        "errors": errors,
        "duration_s": duration_s,
    }

    _save_stats(account, session_stats)

    log.info(
        "=== SESSION END === archived=%d kept=%d errors=%d duration=%ss",
        archived, kept, errors, duration_s,
    )

    return session_stats
