"""
Inbox organizer: categorize every email and move to IMAP folders.

Creates folders on the server and moves emails using COPY+verified+DELETE.
Same safety guarantees as archiver: no delete without confirmed copy.
"""

import re
import logging
import time
from typing import Dict, List, Tuple
from collections import defaultdict

from email_archiver.config import get_password, get_provider
from email_archiver.imap_client import IMAPClient
from email_archiver.logging_setup import setup_logging

logger = logging.getLogger("email_archiver")


def categorize(from_addr: str, subject: str) -> str:
    """Categorize an email into a folder name based on sender/subject."""
    f = from_addr.lower()
    s = subject.lower()

    # Self-sent
    if "justinlacerte@" in f or "jlacerte@solutionsjl" in f:
        return "Notes-personnelles"

    # --- TRAVAIL ---
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
    if "pascal@mecg.ca" in f:
        return "Travail/MECG"
    if "alarmegs.ca" in f:
        return "Travail/AlarmeGS"
    if "congresgatineau.com" in f:
        return "Travail/PalaisCongres"
    if any(x in f for x in [
        "nationalfire.com", "flocor.ca", "emcoltd.com", "bf-tech", "bftechinc",
        "areo-feu.com", "scscanada.ca", "lcccanada.ca", "semfire",
    ]):
        return "Travail/Fournisseurs"
    if any(x in f for x in [
        "omhgatineau.qc.ca", "realstar.ca", "cep-experts", "glatfelter",
        "immeublesdsm.com", "gregoiredesign",
    ]):
        return "Travail/Clients"

    # --- GOUVERNEMENT ---
    if "cnesst" in f:
        return "Gouvernement/CNESST"
    if "mapaq.gouv.qc.ca" in f:
        return "Gouvernement/MAPAQ"
    if "mrcpapineau.com" in f:
        return "Gouvernement/MRC-Papineau"
    if "cldpapineau.ca" in f:
        return "Gouvernement/CLD-Papineau"

    # --- AGRICULTURE ---
    if "upa.qc.ca" in f or "pbq@" in f:
        return "Agriculture/UPA"
    if "fadq.qc.ca" in f:
        return "Agriculture/FADQ"

    # --- FINANCIER ---
    if "desjardins" in f or "scd.desjardins" in f:
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
    if "xplore.ca" in f:
        return "Factures/Xplore"
    if "staples.ca" in f:
        return "Factures/BureauEnGros"
    if "greengeeks" in f:
        return "Factures/GreenGeeks"
    if "caaquebec" in f:
        return "Financier/CAA"

    # --- ASSURANCE ---
    if "charleboistrepanier.com" in f:
        return "Assurance/Charlebois"
    if "laturquoise.ca" in f:
        return "Assurance/Turquoise"
    if "bflcanada.ca" in f:
        return "Assurance/BFL"
    if any(x in f for x in ["intact.ca", "promutuel.ca", "inalco"]):
        return "Assurance"

    # --- COMPTABILITE ---
    if any(x in f for x in ["falardeau", "scfconseils", "fcoulombe@apoint", "dbadea@"]):
        return "Comptabilite"

    # --- EDUCATION ---
    if "cscv.qc.ca" in f or "csdraveurs" in f or "cssd.gouv" in f:
        return "Education"

    # --- PERSONNEL ---
    if "melokiii@" in f or "coutoumelodie" in f or "jomaev@" in f or "cpemillecouleurs" in f:
        return "Personnel/Famille"
    if "cafelabrulerie" in f:
        return "Personnel/Dominique"
    if "orthodontiste" in f:
        return "Personnel/Sante"
    if "mapmyrun" in f:
        return "Personnel/Fitness"

    # Relay iCloud spam
    if "@icloud.com" in f and "_at_" in f:
        return "Spam"

    # --- FACTURES / SERVICES ---
    if "anthropic" in f:
        return "Factures/Anthropic"
    if "google.com" in f and ("payment" in f or "invoice" in f or "workspace" in f):
        return "Factures/Google"
    if "aquavoice.com" in f or "acct_1onzww" in f.lower():
        return "Factures/AquaVoice"
    if "fal.ai" in f or "acct_1hphnx" in f.lower():
        return "Factures/fal"
    if "cloudplatform-noreply@google.com" in f:
        return "Dev-Tech/Google-Cloud"
    if "netlify" in f:
        return "Dev-Tech/Netlify"
    if "docker" in f:
        return "Dev-Tech/Docker"
    if "github.com" in f:
        return "Dev-Tech/GitHub"
    if "cursor" in f or "firecrawl" in f or "livekit" in f:
        return "Dev-Tech"
    if "ollama" in f or "ollama.com" in f:
        return "Dev-Tech/Ollama"
    if "manus.im" in f or "wispr.ai" in f:
        return "Dev-Tech"
    if "claude.com" in f or "claude.ai" in f:
        return "Dev-Tech/Claude"
    if "youtube.com" in f:
        return "Notifications/YouTube"
    if "coinbase" in f or "netcoins" in f:
        return "Crypto"
    if "ultimate-guitar" in f:
        return "Newsletters"
    if "postman.com" in f:
        return "Dev-Tech"
    if "circle.so" in f or "dynamous" in f or "cole-dynamous" in f:
        return "Dev-Tech/Dynamous"
    if "accounts.google.com" in f:
        return "Notifications/Google"
    if "langfuse" in f:
        return "Dev-Tech"
    if "twilio.com" in f:
        return "Dev-Tech/Twilio"
    if "mecg.ca" in f and "justin@mecg.ca" in f:
        return "Travail/MECG"
    if "replit" in f:
        return "Dev-Tech"
    if "openai.com" in f:
        return "Dev-Tech/OpenAI"
    if "notion.so" in f or "notion.com" in f:
        return "Dev-Tech"
    if "brave.com" in f:
        return "Dev-Tech"
    if "slack.com" in f:
        return "Dev-Tech"
    if "fly.io" in f or "render.com" in f or "railway.app" in f:
        return "Dev-Tech"
    if "morgane" in f:
        return "Personnel/Famille"

    # --- DEV / TECH ---
    if any(x in f for x in [
        "supabase", "flutterflow", "vercel.com", "stackoverflow",
        "scribd", "fullstackacademy", "codelobster", "gitcoin",
        "sitepoint", "livecode", "teachable", "filemaker",
        "sage.com", "firefox.com", "koding.com", "iformbuilder",
        "zerionsoftware", "monkeybread", "xojo.com", "koolreport",
        "box.com", "instapaper", "stackblitz", "coupa",
    ]):
        return "Dev-Tech"

    if any(x in f for x in ["aws", "amazon"]) and "no-reply" in f:
        return "Dev-Tech"

    # --- SOCIAL ---
    if "twitter.com" in f:
        return "Social"

    if "linkedin.com" in f:
        return "Social"

    if "meta.com" in f or "facebook" in f:
        return "Social"

    # --- NEWSLETTERS ---
    if any(x in f for x in [
        "quebecloisirs", "eff.org", "drolementinspirant", "shinybud",
        "renaud-bray", "tommorrison", "acces-credit", "pentoncem",
        "tdworld", "logojoy", "intercom-mail", "centraideoutaouais",
    ]):
        return "Newsletters"

    # --- SONDAGES ---
    if any(x in f for x in ["leger360", "legerweb", "surveygizmo", "coursera", "umd.edu"]):
        return "Newsletters"

    # --- NOTIFICATIONS ---
    if any(x in f for x in ["apple.com", "itunes.com"]):
        return "Notifications/Apple"

    if "yahoo.com" in f and "justinlacerte" not in f:
        return "Notifications"

    if "telus" in f:
        return "Factures/Telus"

    if "postmaster@" in f:
        return "Notifications"

    # Default: leave in inbox
    return ""


def run_organize(account: str) -> Dict[str, int]:
    """Organize all inbox emails into categorized IMAP folders.

    Returns dict of {folder: count_moved}.
    """
    log = setup_logging(account)
    provider = get_provider(account)
    batch_size = provider["batch_size"]

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
                    # Parse: (\flags) "/" "folder name"
                    match = re.search(rb'"([^"]+)"$', item)
                    if match:
                        existing_folders.add(match.group(1).decode("utf-8", errors="replace"))

        log.info("Existing folders: %d", len(existing_folders))

        client.select_folder(provider["source_folder"])
        all_uids = client.search_all_uids()

        # Phase 1: classify all emails
        log.info("Phase 1: Classifying %d emails...", len(all_uids))
        uid_to_folder: Dict[bytes, str] = {}
        for i in range(0, len(all_uids), batch_size):
            batch = all_uids[i : i + batch_size]
            try:
                headers = client.fetch_headers(batch)
            except Exception as e:
                log.error("FETCH error batch %d: %s", i, e)
                errors += 1
                continue

            for uid, from_addr, subject in headers:
                folder = categorize(from_addr, subject)
                if folder:
                    uid_to_folder[uid] = folder
                else:
                    skipped += 1

            if (i + len(batch)) % 500 == 0:
                log.info("  Classified %d/%d...", i + len(batch), len(all_uids))

        log.info(
            "Classification done: %d to move, %d stay in inbox",
            len(uid_to_folder), skipped,
        )

        # Phase 2: group by destination folder
        folder_to_uids: Dict[str, List[bytes]] = defaultdict(list)
        for uid, folder in uid_to_folder.items():
            folder_to_uids[folder].append(uid)

        # Phase 3: create missing folders
        folders_needed = set(folder_to_uids.keys())
        for folder in sorted(folders_needed):
            if folder not in existing_folders:
                try:
                    # Quote folder name for IMAP
                    quoted = f'"{folder}"'
                    typ, _ = conn.create(quoted)
                    if typ == "OK":
                        log.info("Created folder: %s", folder)
                        existing_folders.add(folder)
                    else:
                        log.error("Failed to create folder: %s", folder)
                except Exception as e:
                    # Folder might already exist with different case
                    log.warning("Create folder '%s': %s (may already exist)", folder, e)

        # Phase 4: move emails (COPY + verified + DELETE) per folder
        for folder in sorted(folder_to_uids.keys()):
            uids = folder_to_uids[folder]
            log.info("Moving %d emails to '%s'...", len(uids), folder)

            # Process in small batches to avoid timeouts
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
    log.info(
        "=== ORGANIZE END === moved=%d skipped=%d errors=%d duration=%ss",
        total_moved, skipped, errors, duration,
    )

    # Print summary
    print(f"\n{'=' * 50}")
    print(f"  {account.upper()} — Organisation terminée")
    print(f"{'=' * 50}")
    for folder in sorted(moved.keys()):
        print(f"  {moved[folder]:5d}  {folder}")
    print(f"  {'─' * 40}")
    print(f"  {total_moved:5d}  TOTAL déplacés")
    print(f"  {skipped:5d}  Restent dans Inbox")
    print(f"  {errors:5d}  Erreurs")
    print(f"  Durée: {duration}s")

    return dict(moved)
