"""
Inbox organizer: classify every email and move to IMAP folders or archive.

Uses the unified classify() function for all classification decisions.
Creates folders on the server and moves emails using COPY+verified+DELETE.
Same safety guarantees as before: no delete without confirmed copy.
"""

import re
import logging
import time
from typing import Dict, List
from collections import defaultdict

from email_archiver.archiver import save_stats
from email_archiver.classifier import classify
from email_archiver.config import get_password, get_provider
from email_archiver.imap_client import IMAPClient
from email_archiver.logging_setup import setup_logging

logger = logging.getLogger("email_archiver")


def run_organize(account: str) -> Dict[str, int]:
    """Organize all inbox emails: sort into folders + archive noise.

    Uses classify() to determine each email's destination:
      - Folder name → COPY+DELETE to that folder
      - "_archive" → COPY+DELETE to provider's archive folder
      - "" → skip (stays in INBOX)

    Returns dict of {folder: count_moved}.
    """
    log = setup_logging(account)
    provider = get_provider(account)
    batch_size = provider["batch_size"]
    archive_folder = provider["archive_folder"]

    log.info("=== ORGANIZE START === account=%s", account)
    start_time = time.time()

    password = get_password(provider["keychain_service"])
    client = IMAPClient(
        host=provider["host"],
        port=provider["port"],
        login=provider["login"],
        password=password,
    )

    moved: Dict[str, int] = defaultdict(int)
    errors = 0
    skipped = 0

    try:
        client.connect()
        conn = client._conn
        assert conn is not None

        # Get existing folders
        typ, folder_list = conn.list()
        existing_folders = set()
        if folder_list:
            for item in folder_list:
                if isinstance(item, bytes):
                    match = re.search(rb'"([^"]+)"$', item)
                    if match:
                        existing_folders.add(match.group(1).decode("utf-8", errors="replace"))

        log.info("Existing folders: %d", len(existing_folders))

        client.select_folder(provider["source_folder"])
        all_uids = client.search_all_uids()

        # Phase 1: classify all emails
        log.info("Phase 1: Classifying %d emails...", len(all_uids))
        uid_to_dest: Dict[bytes, str] = {}
        consecutive_fetch_errors = 0
        for i in range(0, len(all_uids), batch_size):
            batch = all_uids[i : i + batch_size]
            try:
                headers = client.fetch_headers(batch)
            except Exception as e:
                log.error("FETCH error batch %d: %s", i, e)
                consecutive_fetch_errors += 1
                errors += 1
                if consecutive_fetch_errors >= provider["max_consecutive_errors"]:
                    log.error(
                        "CIRCUIT BREAKER: %d consecutive FETCH errors. STOPPING.",
                        consecutive_fetch_errors,
                    )
                    break
                continue
            consecutive_fetch_errors = 0

            for uid, from_addr, subject in headers:
                dest = classify(from_addr, subject)
                if dest == "_archive":
                    uid_to_dest[uid] = archive_folder
                elif dest:
                    uid_to_dest[uid] = dest
                else:
                    skipped += 1

            if (i + len(batch)) % 500 == 0:
                log.info("  Classified %d/%d...", i + len(batch), len(all_uids))

        log.info(
            "Classification done: %d to move, %d stay in inbox",
            len(uid_to_dest), skipped,
        )

        # Phase 2: group by destination folder
        folder_to_uids: Dict[str, List[bytes]] = defaultdict(list)
        for uid, dest in uid_to_dest.items():
            folder_to_uids[dest].append(uid)

        # Phase 3: create missing folders (skip provider archive — already exists)
        folders_needed = set(folder_to_uids.keys())
        for folder in sorted(folders_needed):
            if folder not in existing_folders and folder != archive_folder:
                try:
                    quoted = f'"{folder}"'
                    typ, _ = conn.create(quoted)
                    if typ == "OK":
                        log.info("Created folder: %s", folder)
                        existing_folders.add(folder)
                    else:
                        log.error("Failed to create folder: %s", folder)
                except Exception as e:
                    log.warning("Create folder '%s': %s (may already exist)", folder, e)

        # Phase 4: move emails (COPY + verified + DELETE) per folder
        for folder in sorted(folder_to_uids.keys()):
            uids = folder_to_uids[folder]
            log.info("Moving %d emails to '%s'...", len(uids), folder)

            for j in range(0, len(uids), 25):
                chunk = uids[j : j + 25]
                copied = []

                for uid in chunk:
                    if client.archive_uid(uid, folder):
                        copied.append(uid)
                    else:
                        log.error("COPY FAILED uid %s to %s", uid.decode(), folder)
                        errors += 1

                if copied:
                    client.mark_deleted(copied)
                    client.expunge()
                    moved[folder] += len(copied)

            log.info("  Done: %d moved to '%s'", moved[folder], folder)

    except Exception as e:
        log.error("Unexpected error: %s", e)
        errors += 1
    finally:
        client.disconnect()

    duration = round(time.time() - start_time, 1)
    total_moved = sum(moved.values())
    archived = moved.get(archive_folder, 0)

    log.info(
        "=== ORGANIZE END === moved=%d archived=%d skipped=%d errors=%d duration=%ss",
        total_moved, archived, skipped, errors, duration,
    )

    # Save stats
    save_stats(account, {
        "moved": total_moved - archived,
        "archived": archived,
        "kept": skipped,
        "errors": errors,
        "duration_s": duration,
    })

    # Print summary
    print(f"\n{'=' * 50}")
    print(f"  {account.upper()} — Organisation terminée")
    print(f"{'=' * 50}")
    for folder in sorted(moved.keys()):
        label = "(archive)" if folder == archive_folder else folder
        print(f"  {moved[folder]:5d}  {label}")
    print(f"  {'─' * 40}")
    print(f"  {total_moved:5d}  TOTAL déplacés")
    print(f"  {skipped:5d}  Restent dans Inbox")
    print(f"  {errors:5d}  Erreurs")
    print(f"  Durée: {duration}s")

    return dict(moved)
