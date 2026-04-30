# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

email-archiver is a Python IMAP email archiver for Gmail, iCloud, and Yahoo. Uses a single persistent IMAP connection per session (1 LOGIN) to avoid Yahoo's aggressive rate-limiting on repeated LOGIN sequences. Zero dependencies — Python 3.9+ stdlib only.

## Commands

```bash
# Run tests (stdlib unittest, no pytest needed)
/opt/homebrew/bin/python3.13 -m unittest discover -s tests -v

# CLI commands
/opt/homebrew/bin/python3.13 -m email_archiver preview yahoo       # read-only, 100 emails
/opt/homebrew/bin/python3.13 -m email_archiver preview icloud -n 20 # read-only, 20 emails
/opt/homebrew/bin/python3.13 -m email_archiver archive yahoo        # archive for real
/opt/homebrew/bin/python3.13 -m email_archiver archive icloud
/opt/homebrew/bin/python3.13 -m email_archiver organize yahoo       # sort inbox into folders
/opt/homebrew/bin/python3.13 -m email_archiver stats all
/opt/homebrew/bin/python3.13 -m email_archiver invoices scan gmail    # scan for invoices (read-only)
/opt/homebrew/bin/python3.13 -m email_archiver invoices download gmail --month 2026-04  # download PDFs
```

System Python is 3.9 (`/usr/bin/python3`). Use Homebrew Python 3.13 at `/opt/homebrew/bin/python3.13`.

## Architecture

`cli.py` → delegates to `archiver.py` (archive/preview/stats), `organizer.py` (organize), `invoice_scanner.py` (invoices scan), or `invoice_downloader.py` (invoices download). All use `IMAPClient` (imap_client.py) for a single persistent IMAP connection, `classifier.py` for pattern-based email classification, and `config.py` for provider configs + macOS Keychain credential retrieval.

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

`classifier.py`: ~80 precompiled regex patterns (from-address + subject). Safe default — `should_archive()` returns False (keep) if no pattern matches. `organizer.py`: ~100 categorization patterns mapping senders to IMAP folder names.
