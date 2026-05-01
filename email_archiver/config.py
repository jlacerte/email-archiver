"""
IMAP account configuration and macOS Keychain credential retrieval.

Provider limits are documented with sources. Credentials are NEVER stored
in files — always retrieved from macOS Keychain at runtime.
"""

import subprocess
import sys
from typing import Dict, Any

# ---------------------------------------------------------------------------
# Provider configurations
#
# YAHOO LIMITS:
#   - Max 3 concurrent IMAP connections per IP
#   - Rapid LOGIN sequences trigger "NO [LIMIT] Rate limit hit" ban
#   - Each connection should do as much work as possible before disconnecting
#   - Source: https://bugzilla.mozilla.org/show_bug.cgi?id=1727971
#   - Source: https://www.getmailbird.com/email-provider-imap-limits-changes/
#
# ICLOUD LIMITS:
#   - More permissive than Yahoo, no documented strict limits
#   - Still rate-limited if abused
#
# GMAIL LIMITS:
#   - Max 15 simultaneous IMAP connections
#   - 2500 MB bandwidth per day for IMAP
#   - Requires App Password (2FA accounts)
#   - Source: https://support.google.com/mail/answer/7126229
# ---------------------------------------------------------------------------

PROVIDERS: Dict[str, Dict[str, Any]] = {
    "gmail": {
        "host": "imap.gmail.com",
        "port": 993,
        "login": "princeorion1@gmail.com",
        "keychain_service": "email-archiver-gmail",
        "source_folder": "INBOX",
        "archive_folder": "[Gmail]/All Mail",
        "batch_size": 50,
        "max_consecutive_errors": 3,
    },
    "icloud": {
        "host": "imap.mail.me.com",
        "port": 993,
        "login": "justinlacerte",
        "keychain_service": "email-archiver-icloud",
        "source_folder": "INBOX",
        "archive_folder": "Archive",
        "batch_size": 50,
        "max_consecutive_errors": 3,
    },
    "yahoo": {
        "host": "imap.mail.yahoo.com",
        "port": 993,
        "login": "justinlacerte@yahoo.ca",
        "keychain_service": "email-archiver-yahoo",
        "source_folder": "Inbox",  # Yahoo uses "Inbox", not "INBOX"
        "archive_folder": "Archive",
        "batch_size": 50,
        "max_consecutive_errors": 3,
    },
}


def get_password(keychain_service: str) -> str:
    """Retrieve password from macOS Keychain.

    Uses `security find-generic-password` — never stores passwords in memory
    longer than necessary.
    """
    result = subprocess.run(
        ["security", "find-generic-password", "-s", keychain_service, "-w"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(
            f"ERROR: Failed to get password from Keychain for '{keychain_service}': "
            f"{result.stderr.strip()}",
            file=sys.stderr,
        )
        sys.exit(1)
    return result.stdout.strip()


def get_provider(name: str) -> Dict[str, Any]:
    """Get provider config by name. Exits if unknown."""
    if name not in PROVIDERS:
        print(
            f"ERROR: Unknown provider '{name}'. Available: {', '.join(PROVIDERS.keys())}",
            file=sys.stderr,
        )
        sys.exit(1)
    return PROVIDERS[name]
