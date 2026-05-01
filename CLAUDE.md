# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

email-archiver is a Python IMAP email archiver for Gmail, iCloud, and Yahoo. Uses a single persistent IMAP connection per session (1 LOGIN) to avoid Yahoo's aggressive rate-limiting on repeated LOGIN sequences. Zero dependencies — Python 3.9+ stdlib only.

## Commands

```bash
# Run tests (stdlib unittest, no pytest needed)
/opt/homebrew/bin/python3.13 -m unittest discover -s tests -v

# CLI commands
/opt/homebrew/bin/python3.13 -m email_archiver preview yahoo       # read-only, show classify() destinations
/opt/homebrew/bin/python3.13 -m email_archiver preview icloud -n 20 # read-only, 20 emails
/opt/homebrew/bin/python3.13 -m email_archiver organize yahoo       # sort inbox into folders + archive noise
/opt/homebrew/bin/python3.13 -m email_archiver stats all
/opt/homebrew/bin/python3.13 -m email_archiver invoices scan gmail    # scan invoice folders (read-only)
/opt/homebrew/bin/python3.13 -m email_archiver invoices download gmail --month 2026-04  # download PDFs
```

System Python is 3.9 (`/usr/bin/python3`). Use Homebrew Python 3.13 at `/opt/homebrew/bin/python3.13`.

## Architecture

`cli.py` → delegates to `archiver.py` (preview/stats), `organizer.py` (organize), `invoice_scanner.py` (invoices scan), or `invoice_downloader.py` (invoices download). All use `IMAPClient` (imap_client.py) for a single persistent IMAP connection, `classifier.py` for unified email classification, and `config.py` for provider configs + macOS Keychain credential retrieval. `organize` is the single command that sorts emails into named folders AND archives noise — there is no separate `archive` command.

## Safety Invariants (non-negotiable)

1. **COPY-verified-before-DELETE**: `archive_uid()` returns True only if COPY succeeded. No email is ever marked `\Deleted` without a confirmed copy.
2. **Circuit breaker**: 3 consecutive FETCH errors → stop entirely. No retry loops.
3. **UIDs only**: All operations use IMAP UIDs, never sequence numbers (sequence numbers shift after EXPUNGE).
4. **Credentials via Keychain only**: `security find-generic-password`. Never store passwords in files.
5. **iCloud STORE quoting**: iCloud requires parenthesized flags `(\\Deleted)` and quoted folder names `"Folder/Name"` in IMAP commands.

## Provider Quirks

**Yahoo**: Max 3 concurrent IMAP connections. Rapid LOGIN sequences trigger `NO [LIMIT] Rate limit hit` ban (source: bugzilla.mozilla.org/1727971). Single persistent connection avoids this entirely.

**iCloud**: Login uses `justinlacerte` (not full email). Folder is `INBOX` (not `Inbox`). Requires quoted folder names with spaces in CREATE/COPY commands.

## Classification

Unified classifier in `classifier.py`. Single entry point: `classify(from_addr, subject) → str`.

Returns:
- Named folder (e.g. `"Financier/BNC"`, `"Travail/Deslauriers"`) — move to that IMAP folder
- `"_archive"` — move to provider's archive folder (generic noise)
- `""` — stay in INBOX (safe default: no match = keep)

Evaluation order (first match wins): Self-sent → Travail → Gouvernement → Agriculture → Financier → Assurance → Comptabilité → Éducation → Personnel → Factures → Dev-Tech → Formations → Social → Crypto → Newsletters → Notifications → Spam → Generic noise → Default (keep).

Key principle: specific sender patterns (steps 1–17) have priority over generic noise patterns (step 18). An email from `noreply@bnc.ca` matches `bnc.ca` → `Financier/BNC`, not `noreply@` → `_archive`.

From-address matching: substring (`in` operator), case-insensitive. Subject matching: compiled regex, case-insensitive (only for generic noise at step 18b).

Legacy wrappers `should_archive()` and `categorize()` delegate to `classify()`.
