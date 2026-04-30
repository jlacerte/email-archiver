"""
Invoice scanner: identify invoices/subscriptions in Gmail inbox.

Two-pass scan:
  Pass 1 — fetch headers (lightweight) for all UIDs, classify by patterns
  Pass 2 — fetch full messages (heavy) only for matches, check for PDF attachments

Read-only: no COPY, no DELETE, no EXPUNGE, no flag changes.
"""

import csv
import email
import email.utils
import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from email_archiver.config import get_password, get_provider
from email_archiver.imap_client import IMAPClient
from email_archiver.logging_setup import setup_logging

logger = logging.getLogger("email_archiver")

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"

# ---------------------------------------------------------------------------
# Invoice detection patterns (separate from classifier.py)
# ---------------------------------------------------------------------------

# From-address substrings that indicate invoice/billing senders
INVOICE_FROM_PATTERNS: List[str] = [
    "anthropic",
    "xplore.ca",
    "staples.ca",
    "greengeeks",
    "aquavoice",
    "fal.ai",
    "telus",
    "google.com",
    "hydro",
    "desjardins",
    "interac.ca",
    "paypal",
]

# Subject regexes that indicate an invoice/receipt/billing email
INVOICE_SUBJECT_STRINGS: List[str] = [
    r"invoice",
    r"facture",
    r"receipt",
    r"re[cç]u",
    r"billing",
    r"payment",
    r"your bill",
    r"relev[eé]",
    r"statement",
    r"order confirmation",
]

_INVOICE_SUBJECT_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in INVOICE_SUBJECT_STRINGS
]

# Provider name normalization: from-address substring -> display name
PROVIDER_MAP: Dict[str, str] = {
    "anthropic": "Anthropic",
    "google.com": "Google",
    "xplore.ca": "Xplore",
    "staples": "BureauEnGros",
    "greengeeks": "GreenGeeks",
    "telus": "Telus",
    "aquavoice": "AquaVoice",
    "fal.ai": "Fal",
    "hydro": "Hydro-Quebec",
    "desjardins": "Desjardins",
    "interac.ca": "Interac",
    "paypal": "PayPal",
}


def is_invoice(from_addr: str, subject: str) -> bool:
    """Returns True if the email looks like an invoice/receipt/billing email.

    Matches on from-address substrings OR subject regexes.
    Safe default: returns False if no pattern matches.
    """
    if not from_addr and not subject:
        return False

    from_lower = from_addr.lower()
    for pattern in INVOICE_FROM_PATTERNS:
        if pattern in from_lower:
            return True

    for pattern in _INVOICE_SUBJECT_PATTERNS:
        if pattern.search(subject):
            return True

    return False


def resolve_provider(from_addr: str) -> str:
    """Resolve a from-address to a normalized provider name.

    Known providers get their display name from PROVIDER_MAP.
    Unknown providers get a capitalized name derived from the email domain.
    """
    from_lower = from_addr.lower()

    for substring, display_name in PROVIDER_MAP.items():
        if substring in from_lower:
            return display_name

    # Unknown provider: derive from domain
    match = re.search(r"@([a-zA-Z0-9.-]+)", from_addr)
    if not match:
        return "Unknown"

    domain = match.group(1).lower()
    parts = domain.split(".")
    # Find the meaningful part: skip subdomains, use second-to-last part
    # e.g., "mail.bigcorp.com" -> "Bigcorp", "e.company.org" -> "Company"
    if len(parts) >= 3:
        name = parts[-2]
    elif len(parts) >= 2:
        name = parts[-2]
    else:
        name = parts[0]

    return name.capitalize()
