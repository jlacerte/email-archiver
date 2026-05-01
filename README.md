# email-archiver

Python IMAP email archiver for **Gmail, iCloud, and Yahoo**. Uses a single persistent IMAP connection (no repeated LOGINs), which avoids Yahoo's aggressive rate-limiting.

## Features

- **Single IMAP connection** per session (1 LOGIN, not hundreds)
- **UID-based operations** (stable across EXPUNGE, unlike sequence numbers)
- **COPY verified before DELETE** — no email is ever deleted without a confirmed copy
- **Circuit breaker** — stops after 3 consecutive errors
- **Zero dependencies** — Python stdlib only (imaplib, email, re, logging)
- **macOS Keychain** for credentials (no plaintext passwords)
- **Preview mode** — classify 100 emails without modifying anything
- **Organize mode** — sort inbox into categorized folders (~100 patterns)

## Usage

```bash
# Archive matching emails (COPY to archive folder, then delete from inbox)
python3 -m email_archiver archive gmail
python3 -m email_archiver archive icloud
python3 -m email_archiver archive yahoo
python3 -m email_archiver archive all

# Preview classification (read-only, 100 emails by default)
python3 -m email_archiver preview gmail
python3 -m email_archiver preview yahoo -n 20

# Organize inbox into categorized folders (Factures/X, Dev-Tech/X, etc.)
python3 -m email_archiver organize gmail
python3 -m email_archiver organize all

# Show cumulative stats
python3 -m email_archiver stats all
```

## Setup

Credentials are stored in macOS Keychain (use an **app-specific password**, not your main account password):

```bash
# Gmail (requires 2FA + app password: https://myaccount.google.com/apppasswords)
security add-generic-password -s email-archiver-gmail -a princeorion1@gmail.com -w "your-app-password"

# iCloud (app-specific password: https://account.apple.com/account/manage)
security add-generic-password -s email-archiver-icloud -a justinlacerte@icloud.com -w "your-app-password"

# Yahoo (app password: https://login.yahoo.com/account/security)
security add-generic-password -s email-archiver-yahoo -a justinlacerte@yahoo.ca -w "your-app-password"
```

Provider configuration (hosts, logins, archive folders) is in `email_archiver/config.py`.

## Provider Limits

| Provider | Connections | Notes |
|---|---|---|
| Gmail | 15 simultaneous | 2500 MB/day IMAP bandwidth. Requires app password (2FA). |
| iCloud | Permissive | Login is `justinlacerte` (not full email). Uses `INBOX` (uppercase). |
| Yahoo | 3 concurrent | Rapid LOGINs trigger `NO [LIMIT] Rate limit hit` ban. Single persistent connection avoids this. Uses `Inbox` (mixed case). |

## How it works

1. Connects to IMAP server (SSL, port 993)
2. Fetches email headers in batches of 50 (From + Subject only, via BODY.PEEK)
3. Classifies each email against ~80 regex patterns (from-address + subject) for `archive`, or ~100 patterns for `organize`
4. For matches: COPY to target folder, verify OK, then mark `\Deleted`
5. EXPUNGE after each batch
6. Logs everything to `logs/<action>-<account>-YYYY-MM-DD.log`

## License

MIT
