"""
Unified email classifier: classify(from_addr, subject) -> str

Returns:
  - A named IMAP folder (e.g. "Financier/BNC", "Travail/Deslauriers")
  - "_archive" for generic noise/promotional emails
  - ""           for unrecognized emails (safe default: stay in INBOX)

Evaluation order (first match wins):
  1. Self-sent
  2. Travail
  3. Gouvernement
  4. Agriculture
  5. Financier
  6. Assurance
  7. Comptabilite
  8. Education
  9. Personnel
  10. Factures
  11. Dev-Tech
  12. Formations
  13. Social
  14. Crypto
  15. Newsletters
  16. Notifications
  17. Spam (iCloud relay)
  18a. Generic noise from-address  -> _archive
  18b. Generic noise subjects       -> _archive
  19. Default -> ""

Safe default: if no pattern matches, the email is KEPT (not archived).

Matching strategy:
  - From-address patterns: substring matching (in operator), case-insensitive
  - Subject patterns: compiled regex, case-insensitive
"""

import re
from typing import List

# ---------------------------------------------------------------------------
# Generic noise from-address patterns (substring, case-insensitive)
# Applied LAST (step 18a) so that specific rules always take priority.
# ---------------------------------------------------------------------------
_NOISE_FROM_PATTERNS: List[str] = [
    "noreply@",
    "no-reply@",
    "notification",
    "newsletter@",
    "marketing@",
    "promo@",
    "donotreply@",
    "mailer-daemon@",
    "bounce@",
    "news@",
    "info@",
    "nepasrepondre",
    "ne-pas-repondre",
    # Bulk-mail subdomains
    "@e.",
    "@email.",
    "@mail.",
    "@newsletter.",
    # Retail / promos
    "@canadiantire",
    "@triangle",
    "@cooperativeplacedumarche",
    "@chefsplate",
    "@clubcage",
    # Research / surveys
    "@opinion.panalyticsgroup",
    # Insurance / financial bulk
    "@mail-corpo.ia.ca",
    # Education
    "@cegep-heritage",
    # Apple privacy relay (spam vector)
    "@privaterelay.appleid",
]

# ---------------------------------------------------------------------------
# Generic noise subject patterns (compiled regex, case-insensitive)
# Applied LAST (step 18b) so that specific rules always take priority.
# ---------------------------------------------------------------------------
_NOISE_SUBJECT_STRINGS: List[str] = [
    r"unsubscribe",
    r"your order",
    r"your receipt",
    r"shipping",
    r"delivery notification",
    r"password reset",
    r"verify your email",
    r"confirm your",
    r"welcome to",
    r"your weekly",
    r"your monthly",
    r"newsletter",
    r"save \d+%",
    r"off today",
    r"limited time",
    r"special offer",
    r"act now",
    r"don.t miss",
    r"last call",
    r"hours left",
    r"days left",
    r"how was your",
    r"rate your",
    r"review your",
    r"feedback",
    r"payment received",
    # Security notifications
    r"security alert",
    r"incident detected",
    r"trusted device",
    r"events notification",
    # French promotional / transactional
    r"offre sp",
    r"rabais",
    r"solde",
    r"aubaine",
    r"promo",
    r"economisez",
    r"prix r",
    r"jour de prime",
    r"vos commentaires",
    r"votre opinion",
    r"votre achat",
    r"comment pouvons",
    r"ailes gratuites",
    r"chasse aux cocos",
    r"menu enfant",
    r"prolongation",
    r"infolettre",
    r"webinaires",
    # Mixed
    r"podcast",
    r"episode",
    r"mot de passe",
    r"app password",
    r"alerte.*pointage",
    r"alerte.*cr.dit",
]

_NOISE_SUBJECT_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _NOISE_SUBJECT_STRINGS]


def classify(from_addr: str, subject: str) -> str:
    """Classify an email into a named folder, '_archive', or '' (keep).

    Args:
        from_addr: The From: header value (email address or display name + address).
        subject:   The Subject: header value.

    Returns:
        A non-empty folder name, "_archive", or "" (stay in INBOX).
    """
    f = from_addr.lower()
    s = subject.lower()

    # -----------------------------------------------------------------------
    # 1. Self-sent
    # -----------------------------------------------------------------------
    if "justinlacerte@" in f or "jlacerte@solutionsjl" in f:
        return "Notes-personnelles"

    # -----------------------------------------------------------------------
    # 2. Travail
    # -----------------------------------------------------------------------
    if "deslauriers1975.ca" in f:
        return "Travail/Deslauriers"
    if "gi-dar" in f or "verificationsgi-dar" in f or "mecaniqueg@" in f:
        return "Travail/GI-DAR"
    if "acq.org" in f or "acqouestqc.org" in f:
        return "Travail/ACQ"
    if "apchq" in f or "cfcpc.ca" in f:
        return "Travail/APCHQ"
    if "gatineau.ca" in f:
        return "Travail/Gatineau"
    if "sqi.gouv.qc.ca" in f:
        return "Travail/SQI"
    if "ssss.gouv.qc.ca" in f:
        return "Travail/CISSSO"
    if "mecg.ca" in f:
        return "Travail/MECG"
    if "alarmegs.ca" in f:
        return "Travail/AlarmeGS"
    if "congresgatineau.com" in f:
        return "Travail/PalaisCongres"
    if any(x in f for x in [
        "coupa",
        "nationalfire.com", "flocor.ca", "emcoltd.com", "bf-tech", "bftechinc",
        "areo-feu.com", "scscanada.ca", "lcccanada.ca", "semfire",
    ]):
        return "Travail/Fournisseurs"
    if any(x in f for x in [
        "omhgatineau.qc.ca", "realstar.ca", "cep-experts", "glatfelter",
        "immeublesdsm.com", "gregoiredesign",
    ]):
        return "Travail/Clients"

    # -----------------------------------------------------------------------
    # 3. Gouvernement
    # -----------------------------------------------------------------------
    if "cnesst" in f:
        return "Gouvernement/CNESST"
    if "mapaq.gouv.qc.ca" in f:
        return "Gouvernement/MAPAQ"
    if "mrcpapineau.com" in f:
        return "Gouvernement/MRC-Papineau"
    if "cldpapineau.ca" in f:
        return "Gouvernement/CLD-Papineau"

    # -----------------------------------------------------------------------
    # 4. Agriculture
    # -----------------------------------------------------------------------
    if "upa.qc.ca" in f or "pbq@" in f:
        return "Agriculture/UPA"
    if "fadq.qc.ca" in f:
        return "Agriculture/FADQ"

    # -----------------------------------------------------------------------
    # 5. Financier
    # -----------------------------------------------------------------------
    if "desjardins" in f:
        return "Financier/Desjardins"
    if "bnc.ca" in f:
        return "Financier/BNC"
    if "interac.ca" in f:
        return "Financier/Interac"
    if "paypal" in f:
        return "Financier/PayPal"
    if "revenuquebec" in f or "servicesquebec" in f:
        return "Financier/RevenuQC"
    if "hydro" in f:
        return "Financier/Hydro-Quebec"
    if "caaquebec" in f:
        return "Financier/CAA"
    if any(x in f for x in ["equifax", "creditkarma", "transunion"]):
        return "Financier/Credit"
    if "fondsftq" in f:
        return "Financier/FondsFTQ"

    # -----------------------------------------------------------------------
    # 6. Assurance
    # -----------------------------------------------------------------------
    if "charleboistrepanier" in f:
        return "Assurance/Charlebois"
    if "laturquoise.ca" in f:
        return "Assurance/Turquoise"
    if "bflcanada" in f:
        return "Assurance/BFL"
    if any(x in f for x in ["intact.ca", "promutuel.ca", "inalco"]):
        return "Assurance"

    # -----------------------------------------------------------------------
    # 7. Comptabilite
    # -----------------------------------------------------------------------
    if any(x in f for x in ["falardeau", "scfconseils", "fcoulombe@apoint", "dbadea@"]):
        return "Comptabilite"

    # -----------------------------------------------------------------------
    # 8. Education
    # -----------------------------------------------------------------------
    if "cscv.qc.ca" in f or "csdraveurs" in f or "cssd.gouv" in f:
        return "Education"

    # -----------------------------------------------------------------------
    # 9. Personnel
    # -----------------------------------------------------------------------
    if any(x in f for x in [
        "melokiii@", "coutoumelodie", "jomaev@", "cpemillecouleurs", "morgane",
    ]):
        return "Personnel/Famille"
    if "cafelabrulerie" in f:
        return "Personnel/Dominique"
    if "orthodontiste" in f:
        return "Personnel/Sante"
    if "mapmyrun" in f:
        return "Personnel/Fitness"
    if "maudeperron" in f:
        return "Personnel/Coaching"

    # -----------------------------------------------------------------------
    # 10. Factures
    # -----------------------------------------------------------------------
    if "anthropic" in f:
        return "Factures/Anthropic"
    if "google.com" in f and any(x in f for x in ["payment", "invoice", "workspace"]):
        return "Factures/Google"
    if "aquavoice.com" in f:
        return "Factures/AquaVoice"
    if "fal.ai" in f:
        return "Factures/fal"
    if "xplore.ca" in f:
        return "Factures/Xplore"
    if "staples.ca" in f:
        return "Factures/BureauEnGros"
    if "greengeeks" in f:
        return "Factures/GreenGeeks"
    if "telus" in f:
        return "Factures/Telus"

    # -----------------------------------------------------------------------
    # 11. Dev-Tech
    # -----------------------------------------------------------------------
    # Specific named sub-folders first
    if "cloudplatform-noreply@google.com" in f:
        return "Dev-Tech/Google-Cloud"
    if "netlify" in f:
        return "Dev-Tech/Netlify"
    if "docker" in f:
        return "Dev-Tech/Docker"
    if "github.com" in f:
        return "Dev-Tech/GitHub"
    if "ollama" in f:
        return "Dev-Tech/Ollama"
    if "claude.com" in f or "claude.ai" in f:
        return "Dev-Tech/Claude"
    if "circle.so" in f or "dynamous" in f or "cole-dynamous" in f:
        return "Dev-Tech/Dynamous"
    if "twilio.com" in f:
        return "Dev-Tech/Twilio"
    if "openai.com" in f:
        return "Dev-Tech/OpenAI"
    if "enom.com" in f or "name-services" in f:
        return "Dev-Tech/Domaines"
    # Bulk Dev-Tech senders (no specific sub-folder)
    if any(x in f for x in [
        "cursor", "firecrawl", "livekit", "supabase", "linode",
        "cloudflare", "gitguardian", "mozilla", "claris", "cpanel@",
        "flutterflow", "vercel.com", "stackoverflow", "scribd",
        "fullstackacademy", "codelobster", "gitcoin", "sitepoint",
        "livecode", "teachable", "filemaker", "sage.com", "firefox.com",
        "koding.com", "iformbuilder", "zerionsoftware", "monkeybread",
        "xojo.com", "koolreport", "box.com", "instapaper", "stackblitz",
        "replit", "notion.so", "notion.com", "brave.com", "slack.com",
        "fly.io", "render.com", "railway.app", "postman.com", "langfuse",
        "manus.im", "wispr.ai",
    ]):
        return "Dev-Tech"
    if any(x in f for x in ["aws", "amazon"]) and any(x in f for x in ["no-reply", "noreply", "marketing"]):
        return "Dev-Tech"

    # -----------------------------------------------------------------------
    # 12. Formations
    # -----------------------------------------------------------------------
    if "vargacombat" in f or "howtofightnow" in f:
        return "Formations"

    # -----------------------------------------------------------------------
    # 13. Social
    # -----------------------------------------------------------------------
    if "twitter.com" in f:
        return "Social"
    if "linkedin.com" in f:
        return "Social"
    if "meta.com" in f or "facebook" in f:
        return "Social"

    # -----------------------------------------------------------------------
    # 14. Crypto
    # -----------------------------------------------------------------------
    if "coinbase" in f or "netcoins" in f or "gonetcoins" in f:
        return "Crypto"

    # -----------------------------------------------------------------------
    # 15. Newsletters
    # -----------------------------------------------------------------------
    if any(x in f for x in [
        "quebecloisirs", "eff.org", "drolementinspirant", "shinybud",
        "renaud-bray", "tommorrison", "acces-credit", "pentoncem",
        "tdworld", "logojoy", "intercom-mail", "centraideoutaouais",
        "leger360", "legerweb", "surveygizmo", "coursera", "umd.edu",
        "ultimate-guitar", "patreon",
    ]):
        return "Newsletters"

    # -----------------------------------------------------------------------
    # 16. Notifications
    # -----------------------------------------------------------------------
    if "youtube.com" in f:
        return "Notifications/YouTube"
    if "accounts.google.com" in f:
        return "Notifications/Google"
    if any(x in f for x in ["apple.com", "itunes.com"]):
        return "Notifications/Apple"
    if "yahoo.com" in f and "justinlacerte" not in f:
        return "Notifications"
    if "postmaster@" in f:
        return "Notifications"

    # -----------------------------------------------------------------------
    # 17. Spam — iCloud privacy relay abuse (@icloud.com with _at_ in address)
    # -----------------------------------------------------------------------
    if "@icloud.com" in f and "_at_" in f:
        return "Spam"

    # -----------------------------------------------------------------------
    # 18a. Generic noise from-address -> _archive
    # -----------------------------------------------------------------------
    for pattern in _NOISE_FROM_PATTERNS:
        if pattern in f:
            return "_archive"

    # -----------------------------------------------------------------------
    # 18b. Generic noise subjects -> _archive
    # -----------------------------------------------------------------------
    for pattern in _NOISE_SUBJECT_PATTERNS:
        if pattern.search(s):
            return "_archive"

    # -----------------------------------------------------------------------
    # 19. Default: stay in INBOX
    # -----------------------------------------------------------------------
    return ""


def should_archive(from_addr: str, subject: str) -> bool:
    """Legacy wrapper: True if the email is generic noise (classify == '_archive').

    Named-folder matches (Financier/BNC, Travail/SQI, etc.) return False —
    those emails are moved to specific folders, not silently archived.

    Safe default: returns False (keep) if no noise pattern matches.
    """
    return classify(from_addr, subject) == "_archive"


def categorize(from_addr: str, subject: str) -> str:
    """Legacy wrapper used by organizer.py.

    Returns the named folder, or '' if classify returns '_archive' or ''.
    Callers interpret '' as "leave in inbox".
    """
    result = classify(from_addr, subject)
    if result == "_archive":
        return ""
    return result
