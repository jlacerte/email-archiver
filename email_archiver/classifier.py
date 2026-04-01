"""
Email classifier: should_archive(from_addr, subject) → bool

~40 from-address patterns + ~40 subject patterns, ported from:
  - scripts/archive-yahoo-imap.py (prototype)
  - scripts/archive-emails.sh (bash archiver)
  - extensions/email-monitor/src/classify.ts (TypeScript reference)

Safe default: if no pattern matches, the email is KEPT (not archived).
"""

import re
from typing import List

# ---------------------------------------------------------------------------
# From-address patterns — archive if sender matches any
# ---------------------------------------------------------------------------
ARCHIVE_FROM: List[str] = [
    # Generic auto-senders
    r"noreply@", r"no-reply@", r"notification", r"newsletter@", r"marketing@",
    r"promo@", r"donotreply@", r"mailer-daemon@", r"bounce@", r"news@", r"info@",
    r"nepasrepondre", r"ne-pas-repondre",
    # Bulk mail subdomains
    r"@e\.", r"@email\.", r"@mail\.", r"@newsletter\.",
    # Retail / promos
    r"@easy\.staples", r"reviews@staples", r"@canadiantire", r"@triangle",
    r"@clubcage", r"@chefsplate", r"@cooperativeplacedumarche",
    # Crypto / fintech notifications
    r"@netcoins", r"@gonetcoins", r"@coinbase\.com", r"@communications\.paypal",
    # Social / podcasts
    r"@patreon", r"@facebookmail", r"@privaterelay\.appleid",
    # Hosting / dev notifications
    r"@linode\.com", r"@em1\.cloudflare\.com", r"@name-services",
    r"@gitguardian", r"@enom\.com", r"@mozilla\.com",
    # Credit bureaus
    r"@equifax", r"@creditkarma", r"@transunion",
    # Marketing / specific senders
    r"@vargacombat\.com", r"@howtofightnow\.com", r"@maudeperron",
    r"@lc\.maudeperron", r"@claris\.com", r"@cegep-heritage",
    r"promotions@.*bnc", r"@mail-corpo\.ia\.ca", r"@opinion\.panalyticsgroup",
    # Coupa supplier portal
    r"@coupa\.com",
]

# ---------------------------------------------------------------------------
# Subject patterns — archive if subject matches any
# ---------------------------------------------------------------------------
ARCHIVE_SUBJECT: List[str] = [
    # English — transactional / promo
    r"unsubscribe", r"your order", r"your receipt", r"shipping",
    r"delivery notification", r"password reset", r"verify your email",
    r"confirm your", r"welcome to", r"your weekly", r"your monthly",
    r"newsletter", r"save \d+%", r"off today", r"limited time",
    r"special offer", r"act now", r"don.t miss", r"last call",
    r"hours left", r"days left", r"how was your", r"rate your",
    r"review your", r"feedback", r"payment received",
    # English — security notifications
    r"security alert", r"incident detected", r"trusted device",
    r"events notification",
    # French
    r"offre sp", r"rabais", r"solde", r"aubaine", r"promo",
    r"economisez", r"prix r", r"jour de prime", r"vos commentaires",
    r"votre opinion", r"votre achat", r"comment pouvons",
    r"ailes gratuites", r"chasse aux cocos", r"menu enfant",
    r"prolongation", r"infolettre", r"webinaires",
    # Mixed
    r"podcast", r"episode", r"mot de passe", r"app password",
    r"alerte.*pointage", r"alerte.*cr.dit",
]

# Pre-compile for performance (called thousands of times per session)
_FROM_PATTERNS = [re.compile(p, re.IGNORECASE) for p in ARCHIVE_FROM]
_SUBJECT_PATTERNS = [re.compile(p, re.IGNORECASE) for p in ARCHIVE_SUBJECT]


def should_archive(from_addr: str, subject: str) -> bool:
    """Returns True if the email matches any archive pattern.

    Safe default: returns False (keep) if no pattern matches.
    """
    from_lower = from_addr.lower()
    subj_lower = subject.lower()

    for pattern in _FROM_PATTERNS:
        if pattern.search(from_lower):
            return True

    for pattern in _SUBJECT_PATTERNS:
        if pattern.search(subj_lower):
            return True

    return False
