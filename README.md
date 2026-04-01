# email-archiver

Python IMAP email archiver for iCloud and Yahoo. Uses a single persistent IMAP connection (no repeated LOGINs), which avoids Yahoo's aggressive rate-limiting.

## Features

- **Single IMAP connection** per session (1 LOGIN, not hundreds)
- **UID-based operations** (stable across EXPUNGE, unlike sequence numbers)
- **COPY verified before DELETE** — no email is ever deleted without a confirmed copy
- **Circuit breaker** — stops after 3 consecutive errors
- **Zero dependencies** — Python stdlib only (imaplib, email, re, logging)
- **macOS Keychain** for credentials (no plaintext passwords)
- **Preview mode** — classify 100 emails without modifying anything

## Usage

```bash
# Archive emails from a specific account
python3 -m email_archiver archive yahoo
python3 -m email_archiver archive icloud
python3 -m email_archiver archive all

# Preview classification (read-only, 1 FETCH of 100 emails)
python3 -m email_archiver preview yahoo

# Show cumulative stats
python3 -m email_archiver stats yahoo
```

## Setup

Credentials are stored in macOS Keychain:

```bash
# iCloud (app-specific password)
security add-generic-password -s himalaya-icloud -a justinlacerte -w "your-app-password"

# Yahoo (app password)
security add-generic-password -s himalaya-yahoo -a justinlacerte@yahoo.ca -w "your-app-password"
```

## How it works

1. Connects to IMAP server (SSL, port 993)
2. Fetches email headers in batches of 50 (From + Subject only, via BODY.PEEK)
3. Classifies each email against ~80 regex patterns (from-address + subject)
4. For matches: COPY to Archive folder, verify OK, then mark \Deleted
5. EXPUNGE after each batch
6. Logs everything with timestamps

## License

MIT
