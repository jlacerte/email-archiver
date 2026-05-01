# Unified Email Classifier — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge three overlapping email classification systems (classifier.py, organizer.py patterns, invoice_scanner.py patterns) into a single `classify()` function that returns a folder name, `"_archive"`, or `""`.

**Architecture:** One unified `classify(from_addr, subject) → str` in classifier.py. Organizer.py uses it for COPY+DELETE operations. Archiver.py loses `run_archive()`, keeps simplified `run_preview()`. Invoice scanner drops its own pattern detection and only scans pre-classified folders. CLI drops the `archive` command.

**Tech Stack:** Python 3.13 stdlib only. unittest for tests. macOS Keychain for credentials.

**Test command:** `/opt/homebrew/bin/python3.13 -m unittest discover -s tests -v`

---

### Task 1: Rewrite classifier.py — tests first

**Files:**
- Create: `tests/test_classifier.py` (full rewrite)
- Create: `email_archiver/classifier.py` (full rewrite)

- [ ] **Step 1: Write the failing tests for classify()**

Replace `tests/test_classifier.py` with:

```python
"""Tests for unified email classifier."""

import unittest

from email_archiver.classifier import classify, should_archive, categorize


class TestClassifyNamedFolders(unittest.TestCase):
    """Test that specific senders map to the correct named folder."""

    # --- Self-sent ---
    def test_self_sent_justinlacerte(self):
        self.assertEqual(classify("justinlacerte@yahoo.ca", "Note"), "Notes-personnelles")

    def test_self_sent_solutionsjl(self):
        self.assertEqual(classify("jlacerte@solutionsjl.com", "Draft"), "Notes-personnelles")

    # --- Travail ---
    def test_travail_deslauriers(self):
        self.assertEqual(classify("info@deslauriers1975.ca", "Projet"), "Travail/Deslauriers")

    def test_travail_gidar(self):
        self.assertEqual(classify("alain@gi-dar.com", "Inspection"), "Travail/GI-DAR")

    def test_travail_acq(self):
        self.assertEqual(classify("formation@acq.org", "Cours"), "Travail/ACQ")

    def test_travail_apchq(self):
        self.assertEqual(classify("info@apchq.com", "Licence"), "Travail/APCHQ")

    def test_travail_cfcpc(self):
        self.assertEqual(classify("admin@cfcpc.ca", "Renouvellement"), "Travail/APCHQ")

    def test_travail_gatineau(self):
        self.assertEqual(classify("permis@gatineau.ca", "Permis"), "Travail/Gatineau")

    def test_travail_sqi(self):
        self.assertEqual(classify("info@sqi.gouv.qc.ca", "Appel d'offres"), "Travail/SQI")

    def test_travail_cissso(self):
        self.assertEqual(classify("admin@ssss.gouv.qc.ca", "Mandat"), "Travail/CISSSO")

    def test_travail_mecg(self):
        self.assertEqual(classify("pascal@mecg.ca", "Projet"), "Travail/MECG")

    def test_travail_alarmgs(self):
        self.assertEqual(classify("admin@alarmegs.ca", "Alarme"), "Travail/AlarmeGS")

    def test_travail_fournisseurs(self):
        self.assertEqual(classify("ventes@nationalfire.com", "PO"), "Travail/Fournisseurs")

    def test_travail_fournisseurs_coupa(self):
        self.assertEqual(classify("noreply@coupa.com", "PO update"), "Travail/Fournisseurs")

    def test_travail_clients(self):
        self.assertEqual(classify("admin@realstar.ca", "Contrat"), "Travail/Clients")

    # --- Gouvernement ---
    def test_gouv_cnesst(self):
        self.assertEqual(classify("info@cnesst.gouv.qc.ca", "Dossier"), "Gouvernement/CNESST")

    def test_gouv_mapaq(self):
        self.assertEqual(classify("info@mapaq.gouv.qc.ca", "Permis"), "Gouvernement/MAPAQ")

    # --- Agriculture ---
    def test_agriculture_upa(self):
        self.assertEqual(classify("info@upa.qc.ca", "Cotisation"), "Agriculture/UPA")

    def test_agriculture_fadq(self):
        self.assertEqual(classify("info@fadq.qc.ca", "Programme"), "Agriculture/FADQ")

    # --- Financier ---
    def test_financier_desjardins(self):
        self.assertEqual(classify("noreply@desjardins.com", "Relevé"), "Financier/Desjardins")

    def test_financier_bnc(self):
        self.assertEqual(classify("telnat@bnc.ca", "Alerte"), "Financier/BNC")

    def test_financier_interac(self):
        self.assertEqual(classify("noreply@payments.interac.ca", "Transfert"), "Financier/Interac")

    def test_financier_paypal(self):
        self.assertEqual(classify("service@paypal.com", "Reçu"), "Financier/PayPal")

    def test_financier_revenuqc(self):
        self.assertEqual(classify("info@revenuquebec.ca", "Avis"), "Financier/RevenuQC")

    def test_financier_hydro(self):
        self.assertEqual(classify("noreply@hydroquebec.com", "Facture"), "Financier/Hydro-Quebec")

    def test_financier_caa(self):
        self.assertEqual(classify("info@caaquebec.com", "Renouvellement"), "Financier/CAA")

    def test_financier_credit(self):
        self.assertEqual(classify("alerts@equifax.ca", "Score"), "Financier/Credit")

    def test_financier_credit_karma(self):
        self.assertEqual(classify("info@creditkarma.com", "Update"), "Financier/Credit")

    def test_financier_transunion(self):
        self.assertEqual(classify("alerts@transunion.ca", "Alert"), "Financier/Credit")

    def test_financier_fondsftq(self):
        self.assertEqual(classify("info@fondsftq.com", "Relevé"), "Financier/FondsFTQ")

    # --- Assurance ---
    def test_assurance_charlebois(self):
        self.assertEqual(classify("info@charleboistrepanier.com", "Police"), "Assurance/Charlebois")

    def test_assurance_intact(self):
        self.assertEqual(classify("noreply@info.intact.ca", "Renouvellement"), "Assurance")

    # --- Comptabilité ---
    def test_comptabilite(self):
        self.assertEqual(classify("admin@scfconseils.com", "T4"), "Comptabilite")

    # --- Éducation ---
    def test_education(self):
        self.assertEqual(classify("info@cscv.qc.ca", "Bulletin"), "Education")

    # --- Personnel ---
    def test_personnel_famille(self):
        self.assertEqual(classify("melokiii@gmail.com", "Salut"), "Personnel/Famille")

    def test_personnel_morgane(self):
        self.assertEqual(classify("morgane@example.com", "Hey"), "Personnel/Famille")

    def test_personnel_coaching(self):
        self.assertEqual(classify("info@maudeperron.com", "Session"), "Personnel/Coaching")

    def test_personnel_sante(self):
        self.assertEqual(classify("rdv@orthodontiste.com", "RDV"), "Personnel/Sante")

    def test_personnel_fitness(self):
        self.assertEqual(classify("noreply@mapmyrun.com", "Run"), "Personnel/Fitness")

    # --- Factures ---
    def test_factures_anthropic(self):
        self.assertEqual(classify("billing@anthropic.com", "Invoice"), "Factures/Anthropic")

    def test_factures_google(self):
        self.assertEqual(classify("payments-noreply@google.com", "Workspace"), "Factures/Google")

    def test_factures_aquavoice(self):
        self.assertEqual(classify("billing@aquavoice.com", "Receipt"), "Factures/AquaVoice")

    def test_factures_fal(self):
        self.assertEqual(classify("billing@fal.ai", "Usage"), "Factures/fal")

    def test_factures_xplore(self):
        self.assertEqual(classify("billing@xplore.ca", "Bill"), "Factures/Xplore")

    def test_factures_staples(self):
        self.assertEqual(classify("orders@staples.ca", "Order"), "Factures/BureauEnGros")

    def test_factures_greengeeks(self):
        self.assertEqual(classify("billing@greengeeks.com", "Renewal"), "Factures/GreenGeeks")

    def test_factures_telus(self):
        self.assertEqual(classify("factures@telus.com", "Votre facture"), "Factures/Telus")

    # --- Dev-Tech ---
    def test_devtech_github(self):
        self.assertEqual(classify("notifications@github.com", "PR merged"), "Dev-Tech/GitHub")

    def test_devtech_claude(self):
        self.assertEqual(classify("noreply@claude.ai", "Welcome"), "Dev-Tech/Claude")

    def test_devtech_openai(self):
        self.assertEqual(classify("noreply@openai.com", "API"), "Dev-Tech/OpenAI")

    def test_devtech_domaines(self):
        self.assertEqual(classify("support@enom.com", "Renewal"), "Dev-Tech/Domaines")

    def test_devtech_domaines_nameservices(self):
        self.assertEqual(classify("noreply@name-services.com", "DNS"), "Dev-Tech/Domaines")

    def test_devtech_bulk_supabase(self):
        self.assertEqual(classify("noreply@supabase.io", "Update"), "Dev-Tech")

    def test_devtech_bulk_linode(self):
        self.assertEqual(classify("noreply@linode.com", "Alert"), "Dev-Tech")

    def test_devtech_bulk_cloudflare(self):
        self.assertEqual(classify("noreply@em1.cloudflare.com", "Alert"), "Dev-Tech")

    def test_devtech_bulk_mozilla(self):
        self.assertEqual(classify("noreply@mozilla.com", "Firefox"), "Dev-Tech")

    def test_devtech_bulk_claris(self):
        self.assertEqual(classify("info@claris.com", "Update"), "Dev-Tech")

    def test_devtech_bulk_cpanel(self):
        self.assertEqual(classify("cpanel@myserver.com", "Backup"), "Dev-Tech")

    def test_devtech_aws(self):
        self.assertEqual(classify("no-reply@aws.amazon.com", "Usage"), "Dev-Tech")

    def test_devtech_aws_marketing(self):
        self.assertEqual(classify("aws-marketing-email@amazon.com", "Webinar"), "Dev-Tech")

    # --- Formations ---
    def test_formations_vargacombat(self):
        self.assertEqual(classify("info@vargacombat.com", "New lesson"), "Formations")

    def test_formations_howtofightnow(self):
        self.assertEqual(classify("info@howtofightnow.com", "Course"), "Formations")

    # --- Social ---
    def test_social_linkedin(self):
        self.assertEqual(classify("notifications@linkedin.com", "Connection"), "Social")

    def test_social_facebook(self):
        self.assertEqual(classify("notification@facebookmail.com", "Activity"), "Social")

    def test_social_twitter(self):
        self.assertEqual(classify("info@twitter.com", "Mention"), "Social")

    # --- Crypto ---
    def test_crypto_coinbase(self):
        self.assertEqual(classify("no-reply@coinbase.com", "Transaction"), "Crypto")

    def test_crypto_netcoins(self):
        self.assertEqual(classify("info@netcoins.ca", "Trade"), "Crypto")

    # --- Newsletters ---
    def test_newsletters_ultimate_guitar(self):
        self.assertEqual(classify("info@ultimate-guitar.com", "Tab"), "Newsletters")

    def test_newsletters_patreon(self):
        self.assertEqual(classify("hello@patreon.com", "New post"), "Newsletters")

    def test_newsletters_eff(self):
        self.assertEqual(classify("info@eff.org", "Privacy"), "Newsletters")

    # --- Notifications ---
    def test_notifications_youtube(self):
        self.assertEqual(classify("noreply@youtube.com", "Upload"), "Notifications/YouTube")

    def test_notifications_apple(self):
        self.assertEqual(classify("noreply@apple.com", "Receipt"), "Notifications/Apple")

    def test_notifications_google(self):
        self.assertEqual(classify("noreply@accounts.google.com", "Alert"), "Notifications/Google")

    # --- Spam ---
    def test_spam_icloud_relay(self):
        self.assertEqual(classify("seller_at_shop@icloud.com", "Buy now"), "Spam")


class TestClassifyArchive(unittest.TestCase):
    """Test that noise patterns produce _archive."""

    # --- Generic from-address noise ---
    def test_noreply(self):
        self.assertEqual(classify("noreply@example.com", "Hello"), "_archive")

    def test_no_reply_dash(self):
        self.assertEqual(classify("no-reply@company.com", "Update"), "_archive")

    def test_newsletter_from(self):
        self.assertEqual(classify("newsletter@news.com", "Weekly digest"), "_archive")

    def test_marketing_from(self):
        self.assertEqual(classify("marketing@brand.com", "New products"), "_archive")

    def test_promo_from(self):
        self.assertEqual(classify("promo@shop.com", "Sale"), "_archive")

    def test_bulk_subdomain_email(self):
        self.assertEqual(classify("promo@email.company.com", "Sale"), "_archive")

    def test_bulk_subdomain_e(self):
        self.assertEqual(classify("news@e.company.com", "Updates"), "_archive")

    def test_canadiantire(self):
        self.assertEqual(classify("deals@canadiantire.ca", "Sale"), "_archive")

    def test_chefsplate(self):
        self.assertEqual(classify("info@chefsplate.com", "Meals"), "_archive")

    def test_cegep_heritage(self):
        self.assertEqual(classify("info@cegep-heritage.qc.ca", "Old"), "_archive")

    def test_privaterelay(self):
        self.assertEqual(classify("noreply@privaterelay.appleid.com", "Promo"), "_archive")

    # --- Subject-based noise ---
    def test_subject_unsubscribe(self):
        self.assertEqual(classify("sender@x.com", "Click to unsubscribe"), "_archive")

    def test_subject_your_order(self):
        self.assertEqual(classify("shop@x.com", "Your order has shipped"), "_archive")

    def test_subject_password_reset(self):
        self.assertEqual(classify("auth@x.com", "Password reset request"), "_archive")

    def test_subject_newsletter(self):
        self.assertEqual(classify("sender@x.com", "Weekly newsletter"), "_archive")

    def test_subject_save_percent(self):
        self.assertEqual(classify("shop@x.com", "Save 50% today only"), "_archive")

    def test_subject_limited_time(self):
        self.assertEqual(classify("shop@x.com", "Limited time offer!"), "_archive")

    def test_subject_security_alert(self):
        self.assertEqual(classify("security@x.com", "Security alert for your account"), "_archive")

    def test_subject_french_offre(self):
        self.assertEqual(classify("shop@x.com", "Offre spéciale du jour"), "_archive")

    def test_subject_french_rabais(self):
        self.assertEqual(classify("shop@x.com", "Rabais de 30%"), "_archive")

    def test_subject_french_infolettre(self):
        self.assertEqual(classify("shop@x.com", "Infolettre de mars"), "_archive")

    def test_subject_mot_de_passe(self):
        self.assertEqual(classify("auth@x.com", "Votre mot de passe"), "_archive")

    def test_subject_podcast(self):
        self.assertEqual(classify("pod@x.com", "New podcast episode"), "_archive")

    def test_subject_payment_received(self):
        self.assertEqual(classify("unknown@x.com", "Payment received"), "_archive")


class TestClassifyKeep(unittest.TestCase):
    """Test that unrecognized emails stay in INBOX (safe default)."""

    def test_personal_email(self):
        self.assertEqual(classify("mom@gmail.com", "Dinner tonight?"), "")

    def test_work_email(self):
        self.assertEqual(classify("boss@company.com", "Meeting at 3pm"), "")

    def test_friend(self):
        self.assertEqual(classify("pascal@hotmail.com", "Hey!"), "")

    def test_empty(self):
        self.assertEqual(classify("", ""), "")

    def test_unknown_sender_neutral_subject(self):
        self.assertEqual(classify("unknown@random.org", "Hello there"), "")


class TestClassifyPriority(unittest.TestCase):
    """Specific sender patterns must shadow generic noise patterns."""

    def test_noreply_bnc_goes_to_financier_not_archive(self):
        """noreply@ is noise, but bnc.ca is specific — specific wins."""
        self.assertEqual(classify("noreply@bnc.ca", "Alerte"), "Financier/BNC")

    def test_nepasrepondre_desjardins_goes_to_financier(self):
        """nepasrepondre is noise, but desjardins is specific — specific wins."""
        self.assertEqual(classify("nepasrepondre@desjardins.com", "Relevé"), "Financier/Desjardins")

    def test_noreply_coinbase_goes_to_crypto(self):
        """noreply@ is noise, but coinbase is specific — specific wins."""
        self.assertEqual(classify("noreply@coinbase.com", "Trade"), "Crypto")

    def test_notification_facebookmail_goes_to_social(self):
        """notification is noise, but facebookmail is specific — specific wins."""
        self.assertEqual(classify("notification@facebookmail.com", "Post"), "Social")

    def test_noreply_greengeeks_goes_to_factures(self):
        self.assertEqual(classify("noreply@greengeeks.com", "Renewal"), "Factures/GreenGeeks")

    def test_info_intact_goes_to_assurance(self):
        """info@ is noise, but intact.ca is specific — specific wins."""
        self.assertEqual(classify("info@intact.ca", "Policy"), "Assurance")

    def test_google_no_billing_is_not_facture(self):
        """google.com without payment/invoice/workspace keywords is NOT a facture."""
        result = classify("calendar@google.com", "Meeting reminder")
        self.assertNotEqual(result, "Factures/Google")


class TestLegacyWrappers(unittest.TestCase):
    """Legacy should_archive() and categorize() wrappers."""

    def test_should_archive_true_for_noise(self):
        self.assertTrue(should_archive("noreply@example.com", "Hello"))

    def test_should_archive_false_for_folder(self):
        self.assertFalse(should_archive("billing@anthropic.com", "Invoice"))

    def test_should_archive_false_for_keep(self):
        self.assertFalse(should_archive("mom@gmail.com", "Dinner?"))

    def test_categorize_returns_folder(self):
        self.assertEqual(categorize("billing@anthropic.com", "Invoice"), "Factures/Anthropic")

    def test_categorize_returns_empty_for_archive(self):
        self.assertEqual(categorize("noreply@example.com", "Hello"), "")

    def test_categorize_returns_empty_for_keep(self):
        self.assertEqual(categorize("mom@gmail.com", "Dinner?"), "")

    def test_partial_match_not_enough(self):
        """info@ should not match information-desk@ (no @ after info)."""
        self.assertFalse(should_archive("information-desk@company.com", "Inquiry"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/opt/homebrew/bin/python3.13 -m unittest tests.test_classifier -v`
Expected: FAIL — `classify` not defined (old classifier.py only has `should_archive`)

- [ ] **Step 3: Implement classify() in classifier.py**

Replace `email_archiver/classifier.py` with:

```python
"""
Unified email classifier: classify(from_addr, subject) → destination.

Single classification function that returns:
  - Folder name (e.g., "Travail/Deslauriers") — move to that IMAP folder
  - "_archive" — move to provider's archive folder
  - "" — leave in INBOX (no match, safe default)

Merges patterns from the former classifier.py (should_archive) and
organizer.py (categorize) into one evaluation with clear priority:
specific sender patterns (steps 1–17) shadow generic noise patterns (step 18).
"""

import re
from typing import List

# ---------------------------------------------------------------------------
# Generic noise from-address patterns — archive if sender matches any
# These are checked AFTER all specific sender patterns (steps 1–17).
# ---------------------------------------------------------------------------
_NOISE_FROM_PATTERNS: List[str] = [
    # Generic auto-senders
    "noreply@", "no-reply@", "notification", "newsletter@", "marketing@",
    "promo@", "donotreply@", "mailer-daemon@", "bounce@", "news@", "info@",
    "nepasrepondre", "ne-pas-repondre",
    # Bulk mail subdomains
    "@e.", "@email.", "@mail.", "@newsletter.",
    # Retail / promos (no folder value)
    "@canadiantire", "@triangle",
    "@cooperativeplacedumarche", "@chefsplate", "@clubcage",
    # Surveys / marketing with no folder value
    "@opinion.panalyticsgroup", "@mail-corpo.ia.ca",
    # Old / irrelevant
    "@cegep-heritage", "@privaterelay.appleid",
]

# ---------------------------------------------------------------------------
# Subject patterns — archive if subject matches (compiled regex)
# Only checked for emails NOT matched by from-address patterns above.
# ---------------------------------------------------------------------------
_NOISE_SUBJECT_STRINGS: List[str] = [
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

_NOISE_SUBJECT_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _NOISE_SUBJECT_STRINGS]


def classify(from_addr: str, subject: str) -> str:
    """Classify an email into a destination.

    Returns:
      - Folder name (e.g., "Travail/Deslauriers", "Factures/Anthropic")
      - "_archive" — move to provider's archive folder
      - "" — leave in INBOX (no match)

    Evaluation: specific sender patterns (steps 1–17) have priority over
    generic noise patterns (step 18). First match wins.
    """
    f = from_addr.lower()
    s = subject.lower()

    # --- 1. SELF-SENT ---
    if "justinlacerte@" in f or "jlacerte@solutionsjl" in f:
        return "Notes-personnelles"

    # --- 2. TRAVAIL ---
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
        "nationalfire.com", "flocor.ca", "emcoltd.com", "bf-tech", "bftechinc",
        "areo-feu.com", "scscanada.ca", "lcccanada.ca", "semfire", "coupa",
    ]):
        return "Travail/Fournisseurs"
    if any(x in f for x in [
        "omhgatineau.qc.ca", "realstar.ca", "cep-experts", "glatfelter",
        "immeublesdsm.com", "gregoiredesign",
    ]):
        return "Travail/Clients"

    # --- 3. GOUVERNEMENT ---
    if "cnesst" in f:
        return "Gouvernement/CNESST"
    if "mapaq.gouv.qc.ca" in f:
        return "Gouvernement/MAPAQ"
    if "mrcpapineau.com" in f:
        return "Gouvernement/MRC-Papineau"
    if "cldpapineau.ca" in f:
        return "Gouvernement/CLD-Papineau"

    # --- 4. AGRICULTURE ---
    if "upa.qc.ca" in f or "pbq@" in f:
        return "Agriculture/UPA"
    if "fadq.qc.ca" in f:
        return "Agriculture/FADQ"

    # --- 5. FINANCIER ---
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

    # --- 6. ASSURANCE ---
    if "charleboistrepanier.com" in f:
        return "Assurance/Charlebois"
    if "laturquoise.ca" in f:
        return "Assurance/Turquoise"
    if "bflcanada.ca" in f:
        return "Assurance/BFL"
    if any(x in f for x in ["intact.ca", "promutuel.ca", "inalco"]):
        return "Assurance"

    # --- 7. COMPTABILITÉ ---
    if any(x in f for x in ["falardeau", "scfconseils", "fcoulombe@apoint", "dbadea@"]):
        return "Comptabilite"

    # --- 8. ÉDUCATION ---
    if "cscv.qc.ca" in f or "csdraveurs" in f or "cssd.gouv" in f:
        return "Education"

    # --- 9. PERSONNEL ---
    if any(x in f for x in ["melokiii@", "coutoumelodie", "jomaev@", "cpemillecouleurs"]):
        return "Personnel/Famille"
    if "morgane" in f:
        return "Personnel/Famille"
    if "cafelabrulerie" in f:
        return "Personnel/Dominique"
    if "orthodontiste" in f:
        return "Personnel/Sante"
    if "mapmyrun" in f:
        return "Personnel/Fitness"
    if any(x in f for x in ["maudeperron", "lc.maudeperron"]):
        return "Personnel/Coaching"

    # --- 10. FACTURES / SERVICES ---
    if "anthropic" in f:
        return "Factures/Anthropic"
    if "google.com" in f and any(x in f for x in ["payment", "invoice", "workspace"]):
        return "Factures/Google"
    if "aquavoice.com" in f or "acct_1onzww" in f:
        return "Factures/AquaVoice"
    if "fal.ai" in f or "acct_1hphnx" in f:
        return "Factures/fal"
    if "xplore.ca" in f:
        return "Factures/Xplore"
    if "staples.ca" in f:
        return "Factures/BureauEnGros"
    if "greengeeks" in f:
        return "Factures/GreenGeeks"
    if "telus" in f:
        return "Factures/Telus"

    # --- 11. DEV-TECH ---
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
    if any(x in f for x in ["circle.so", "dynamous", "cole-dynamous"]):
        return "Dev-Tech/Dynamous"
    if "twilio.com" in f:
        return "Dev-Tech/Twilio"
    if "openai.com" in f:
        return "Dev-Tech/OpenAI"
    if any(x in f for x in ["enom.com", "name-services"]):
        return "Dev-Tech/Domaines"
    if any(x in f for x in [
        "cursor", "firecrawl", "livekit", "manus.im", "wispr.ai",
        "postman.com", "langfuse", "replit", "notion.so", "notion.com",
        "brave.com", "slack.com", "fly.io", "render.com", "railway.app",
        "supabase", "flutterflow", "vercel.com", "stackoverflow",
        "scribd", "fullstackacademy", "codelobster", "gitcoin",
        "sitepoint", "livecode", "teachable", "filemaker",
        "sage.com", "firefox.com", "koding.com", "iformbuilder",
        "zerionsoftware", "monkeybread", "xojo.com", "koolreport",
        "box.com", "instapaper", "stackblitz",
        "linode", "cloudflare", "gitguardian", "mozilla.com",
        "claris.com", "cpanel@",
    ]):
        return "Dev-Tech"
    if any(x in f for x in ["aws", "amazon"]) and any(x in f for x in [
        "no-reply", "noreply", "marketing",
    ]):
        return "Dev-Tech"

    # --- 12. FORMATIONS ---
    if any(x in f for x in ["vargacombat", "howtofightnow"]):
        return "Formations"

    # --- 13. SOCIAL ---
    if "twitter.com" in f or "linkedin.com" in f:
        return "Social"
    if "meta.com" in f or "facebook" in f:
        return "Social"

    # --- 14. CRYPTO ---
    if "coinbase" in f or "netcoins" in f or "gonetcoins" in f:
        return "Crypto"

    # --- 15. NEWSLETTERS ---
    if any(x in f for x in [
        "quebecloisirs", "eff.org", "drolementinspirant", "shinybud",
        "renaud-bray", "tommorrison", "acces-credit", "pentoncem",
        "tdworld", "logojoy", "intercom-mail", "centraideoutaouais",
        "leger360", "legerweb", "surveygizmo", "coursera", "umd.edu",
        "ultimate-guitar", "patreon",
    ]):
        return "Newsletters"

    # --- 16. NOTIFICATIONS ---
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

    # --- 17. SPAM ---
    if "@icloud.com" in f and "_at_" in f:
        return "Spam"

    # --- 18a. GENERIC NOISE — from-address patterns ---
    for noise in _NOISE_FROM_PATTERNS:
        if noise in f:
            return "_archive"

    # --- 18b. GENERIC NOISE — subject patterns ---
    for pattern in _NOISE_SUBJECT_PATTERNS:
        if pattern.search(s):
            return "_archive"

    # --- 19. DEFAULT — stay in INBOX ---
    return ""


# ---------------------------------------------------------------------------
# Legacy wrappers (backward compatibility during transition)
# ---------------------------------------------------------------------------

def should_archive(from_addr: str, subject: str) -> bool:
    """Returns True if classify() would archive.

    Legacy wrapper — use classify() directly in new code.
    """
    return classify(from_addr, subject) == "_archive"


def categorize(from_addr: str, subject: str) -> str:
    """Returns folder name or '' (excludes _archive).

    Legacy wrapper — use classify() directly in new code.
    """
    result = classify(from_addr, subject)
    return "" if result == "_archive" else result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/opt/homebrew/bin/python3.13 -m unittest tests.test_classifier -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add email_archiver/classifier.py tests/test_classifier.py
git commit -m "feat: unified classify() merging classifier + organizer patterns

Single function replaces should_archive() and categorize() with one
evaluation. Specific sender patterns shadow generic noise patterns.
Returns folder name, '_archive', or '' (keep in INBOX)."
```

---

### Task 2: Update archiver.py — remove run_archive, update run_preview

**Files:**
- Modify: `email_archiver/archiver.py`

- [ ] **Step 1: Update archiver.py**

Replace the entire `email_archiver/archiver.py` with:

```python
"""
Archiver: preview classification and manage stats.

run_archive() has been removed — use `organize` which handles both
folder sorting and noise archiving via the unified classify() function.
"""

import json
import logging
import time
from pathlib import Path
from typing import Dict, Any

from email_archiver.classifier import classify
from email_archiver.config import get_password, get_provider
from email_archiver.imap_client import IMAPClient
from email_archiver.logging_setup import setup_logging

STATS_DIR = Path(__file__).resolve().parent.parent / "logs"


def _load_stats(account: str) -> Dict[str, Any]:
    stats_file = STATS_DIR / f"archive-{account}-stats.json"
    if stats_file.exists():
        with open(stats_file) as f:
            return json.load(f)
    return {
        "total_archived": 0,
        "total_kept": 0,
        "total_errors": 0,
        "last_session": "never",
    }


def save_stats(account: str, session_stats: Dict[str, Any]) -> None:
    """Save session stats to disk (called by organizer after run_organize)."""
    STATS_DIR.mkdir(parents=True, exist_ok=True)
    prev = _load_stats(account)
    stats = {
        "total_archived": prev["total_archived"] + session_stats.get("archived", 0),
        "total_kept": prev["total_kept"] + session_stats.get("kept", 0),
        "total_errors": prev["total_errors"] + session_stats.get("errors", 0),
        "last_session": time.strftime("%Y-%m-%d %H:%M:%S"),
        "last_session_archived": session_stats.get("archived", 0),
        "last_session_kept": session_stats.get("kept", 0),
        "last_session_moved": session_stats.get("moved", 0),
        "last_session_errors": session_stats.get("errors", 0),
        "last_session_duration_s": session_stats.get("duration_s", 0),
    }
    stats_file = STATS_DIR / f"archive-{account}-stats.json"
    tmp_file = stats_file.with_suffix(".tmp")
    with open(tmp_file, "w") as f:
        json.dump(stats, f, indent=2)
    tmp_file.rename(stats_file)


def show_stats(account: str) -> None:
    """Print cumulative stats for an account."""
    stats = _load_stats(account)
    print(f"\n=== Stats for {account} ===")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    print()


def run_preview(account: str, limit: int = 100) -> None:
    """Preview mode: fetch up to `limit` emails, classify, print results.

    Read-only — no COPY, no DELETE, no EXPUNGE. One FETCH only.
    Shows destination folder for each email.
    """
    log = setup_logging(account)
    provider = get_provider(account)

    log.info("=== PREVIEW START === account=%s limit=%d", account, limit)

    password = get_password(provider["keychain_service"])
    client = IMAPClient(
        host=provider["host"],
        port=provider["port"],
        login=provider["login"],
        password=password,
    )

    try:
        client.connect()
        client.select_folder(provider["source_folder"])
        all_uids = client.search_all_uids()

        uids_to_fetch = all_uids[:limit]
        headers = client.fetch_headers(uids_to_fetch)

        folder_count = 0
        archive_count = 0
        keep_count = 0
        for _uid, from_addr, subject in headers:
            dest = classify(from_addr, subject)
            if dest == "_archive":
                tag = "_archive"
                archive_count += 1
            elif dest == "":
                tag = "KEEP"
                keep_count += 1
            else:
                tag = dest
                folder_count += 1
            log.info("[%s] From: %s | Subject: %s", tag, from_addr, subject[:60])

        log.info(
            "=== PREVIEW END === %d to folders, %d to archive, %d keep "
            "(of %d fetched, %d total in folder)",
            folder_count, archive_count, keep_count,
            len(headers), len(all_uids),
        )
    except Exception as e:
        log.error("Preview failed: %s", e)
        raise
    finally:
        client.disconnect()
```

- [ ] **Step 2: Run full test suite**

Run: `/opt/homebrew/bin/python3.13 -m unittest discover -s tests -v`
Expected: All tests pass (archiver tests are indirect via CLI — no dedicated test file)

- [ ] **Step 3: Commit**

```bash
git add email_archiver/archiver.py
git commit -m "refactor: remove run_archive(), update preview to show destinations

run_archive() removed — organize now handles both folder sorting and
noise archiving. run_preview() uses classify() and shows the destination
folder for each email. save_stats() made public for organizer to call."
```

---

### Task 3: Simplify organizer.py — use classify()

**Files:**
- Modify: `email_archiver/organizer.py`

- [ ] **Step 1: Rewrite organizer.py**

Replace the entire `email_archiver/organizer.py` with:

```python
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
        for i in range(0, len(all_uids), batch_size):
            batch = all_uids[i : i + batch_size]
            try:
                headers = client.fetch_headers(batch)
            except Exception as e:
                log.error("FETCH error batch %d: %s", i, e)
                errors += 1
                continue

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
```

- [ ] **Step 2: Run full test suite**

Run: `/opt/homebrew/bin/python3.13 -m unittest discover -s tests -v`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add email_archiver/organizer.py
git commit -m "refactor: organizer uses unified classify() for all decisions

Removed local categorize() function. organize now handles both folder
sorting and noise archiving in a single pass via classify(). Stats
saved after each session."
```

---

### Task 4: Simplify invoice_scanner.py — remove patterns and INBOX scanning

**Files:**
- Modify: `email_archiver/invoice_scanner.py`
- Modify: `tests/test_invoice_scanner.py`

- [ ] **Step 1: Update invoice_scanner.py**

Remove `is_invoice()`, `INVOICE_FROM_PATTERNS`, `INVOICE_SUBJECT_STRINGS`, `_INVOICE_SUBJECT_PATTERNS`, and `_scan_inbox()`. Update `run_scan()` to only scan `Factures/*` and `Financier/*` folders.

Replace the entire `email_archiver/invoice_scanner.py` with:

```python
"""
Invoice scanner: find invoices in pre-classified IMAP folders.

Scans Factures/* and Financier/* folders (populated by organize).
All emails in these folders are already invoices — no classification needed.
Checks each for PDF attachments and generates reports.

Read-only: no COPY, no DELETE, no EXPUNGE, no flag changes.
"""

import csv
import email
import email.message
import email.utils
import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from email_archiver.config import get_password, get_provider
from email_archiver.imap_client import IMAPClient, _decode_header_value
from email_archiver.logging_setup import setup_logging

logger = logging.getLogger("email_archiver")

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"

# Folder prefixes to scan for invoices (populated by organize)
SCAN_FOLDER_PREFIXES: List[str] = ["Factures", "Financier"]

# Provider name normalization: from-address substring -> display name
PROVIDER_MAP: Dict[str, str] = {
    "anthropic": "Anthropic",
    "payments-noreply@google.com": "Google",
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


def resolve_provider(from_addr: str) -> str:
    """Resolve a from-address to a normalized provider name.

    Known providers get their display name from PROVIDER_MAP.
    Unknown providers get a capitalized name derived from the email domain.
    """
    from_lower = from_addr.lower()

    for substring, display_name in PROVIDER_MAP.items():
        if substring in from_lower:
            return display_name

    match = re.search(r"@([a-zA-Z0-9.-]+)", from_addr)
    if not match:
        return "Unknown"

    domain = match.group(1).lower()
    parts = domain.split(".")
    if len(parts) >= 2:
        name = parts[-2]
    else:
        name = parts[0]

    return name.capitalize()


def extract_pdf_info(msg: email.message.Message) -> Dict[str, Any]:
    """Extract PDF attachment info from a parsed email message.

    Returns a dict with:
      - has_pdf: bool
      - link_only: bool (True if no PDF but HTML body contains a link)
      - pdf_files: list of {filename, size_bytes}
    """
    pdf_files: List[Dict[str, Any]] = []

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            filename = part.get_filename()

            is_pdf = (
                content_type == "application/pdf"
                or (filename and filename.lower().endswith(".pdf"))
            )
            if is_pdf and filename:
                payload = part.get_payload(decode=True)
                size = len(payload) if payload else 0
                pdf_files.append({"filename": filename, "size_bytes": size})

    if pdf_files:
        return {"has_pdf": True, "link_only": False, "pdf_files": pdf_files}

    # Check for invoice links in HTML body
    link_only = False
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                html = part.get_payload(decode=True)
                if html and re.search(rb"https?://[^\s\"']+invoice", html, re.IGNORECASE):
                    link_only = True
                    break
    else:
        content_type = msg.get_content_type()
        if content_type == "text/html":
            html = msg.get_payload(decode=True)
            if html and re.search(rb"https?://[^\s\"']+invoice", html, re.IGNORECASE):
                link_only = True

    return {"has_pdf": False, "link_only": link_only, "pdf_files": []}


def build_report(
    account: str,
    invoices: List[Dict[str, Any]],
    total_scanned: int,
) -> Dict[str, Any]:
    """Build the structured scan report from invoice data.

    Returns the full report dict ready for JSON serialization.
    """
    providers: Dict[str, Dict[str, Any]] = {}

    for inv in invoices:
        prov = inv["provider"]
        if prov not in providers:
            providers[prov] = {
                "count": 0,
                "has_pdf_attachments": False,
                "link_only": False,
                "months": [],
            }

        providers[prov]["count"] += 1

        if inv["has_pdf"]:
            providers[prov]["has_pdf_attachments"] = True
        if inv["link_only"]:
            providers[prov]["link_only"] = True

        if inv.get("date"):
            month = inv["date"][:7]
            if month not in providers[prov]["months"]:
                providers[prov]["months"].append(month)

    for prov_data in providers.values():
        prov_data["months"].sort()

    return {
        "scan_date": datetime.now().strftime("%Y-%m-%d"),
        "account": account,
        "total_emails_scanned": total_scanned,
        "invoices_found": len(invoices),
        "providers": providers,
        "invoices": invoices,
    }


def _write_reports(report: Dict[str, Any], account: str) -> Tuple[Path, Path]:
    """Write scan report to JSON and TXT files.

    Uses atomic write (tmp + rename) for the JSON file.
    Returns (json_path, txt_path).
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    json_path = REPORTS_DIR / f"{account}-invoices-scan.json"
    tmp_path = json_path.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    tmp_path.rename(json_path)

    txt_path = REPORTS_DIR / f"{account}-invoices-scan.txt"
    lines = [
        f"=== Scan des factures — {account.upper()} ===",
        f"Date du scan : {report['scan_date']}",
        f"Courriels scannés : {report['total_emails_scanned']}",
        f"Factures trouvées : {report['invoices_found']}",
        "",
        "ABONNEMENTS IDENTIFIÉS :",
    ]

    for prov_name in sorted(report["providers"].keys()):
        prov = report["providers"][prov_name]
        count = prov["count"]
        if prov["has_pdf_attachments"]:
            tag = "[PDF]"
        elif prov.get("link_only"):
            tag = "[LIEN]"
        else:
            tag = "[?]"
        lines.append(f"  {prov_name:<20s} {count} factures  {tag}")

    link_only_provs = [
        name for name, data in report["providers"].items()
        if not data["has_pdf_attachments"] and data.get("link_only")
    ]
    if link_only_provs:
        lines.append("")
        lines.append("SANS PDF (à télécharger manuellement) :")
        for name in sorted(link_only_provs):
            lines.append(f"  {name} — liens dans les courriels")

    lines.append("")

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return json_path, txt_path


def _provider_from_folder(folder: str) -> Optional[str]:
    """Derive provider name from a Factures/ProviderName folder path.

    Returns the provider part (e.g., "Anthropic" from "Factures/Anthropic"),
    or None if the folder doesn't match the pattern.
    """
    parts = folder.split("/")
    if len(parts) >= 2 and parts[0] in ("Factures", "Financier"):
        return parts[-1]
    return None


def _scan_folder(
    client: IMAPClient,
    folder: str,
    max_errors: int,
    log: logging.Logger,
) -> Tuple[List[Dict[str, Any]], int]:
    """Scan a pre-classified folder (Factures/*, Financier/*).

    All emails in these folders are already invoices — no classification needed.
    Provider name is derived from the folder name.

    Returns (invoices_list, total_emails_in_folder).
    """
    count = client.select_folder(folder)
    if count == 0:
        return [], 0

    all_uids = client.search_all_uids()
    total = len(all_uids)
    consecutive_errors = 0
    invoices: List[Dict[str, Any]] = []

    folder_provider = _provider_from_folder(folder)

    log.info("Scanning folder '%s': %d emails...", folder, total)

    for uid in all_uids:
        msg = client.fetch_message(uid)
        if msg is None:
            consecutive_errors += 1
            if consecutive_errors >= max_errors:
                log.error(
                    "CIRCUIT BREAKER: %d consecutive FETCH errors in '%s'. STOPPING.",
                    consecutive_errors, folder,
                )
                break
            continue

        consecutive_errors = 0

        from_addr = _decode_header_value(msg.get("From", "")).lower()
        subject = _decode_header_value(msg.get("Subject", ""))
        date_str = _extract_date(msg)
        provider_name = folder_provider or resolve_provider(from_addr)
        pdf_info = extract_pdf_info(msg)

        invoices.append({
            "uid": uid.decode() if isinstance(uid, bytes) else str(uid),
            "from": from_addr,
            "provider": provider_name,
            "subject": subject,
            "date": date_str,
            "has_pdf": pdf_info["has_pdf"],
            "link_only": pdf_info["link_only"],
            "pdf_files": pdf_info["pdf_files"],
            "folder": folder,
        })
        log.info(
            "[INVOICE] %s | %s | %s | PDF=%s | folder=%s",
            provider_name, from_addr, subject[:50],
            "yes" if pdf_info["has_pdf"] else "no", folder,
        )

    return invoices, total


def _extract_date(msg: email.message.Message) -> str:
    """Extract date from email headers as YYYY-MM-DD string."""
    date_header = msg.get("Date", "")
    if date_header:
        try:
            dt = email.utils.parsedate_to_datetime(date_header)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            pass
    return ""


def run_scan(account: str) -> Dict[str, Any]:
    """Run invoice scan across pre-classified folders (read-only).

    Discovers Factures/* and Financier/* folders (populated by organize)
    and scans each for PDF attachments.

    Returns the scan report dict.
    """
    log = setup_logging(account)
    provider = get_provider(account)
    max_errors = provider["max_consecutive_errors"]

    log.info("=== INVOICE SCAN START === account=%s", account)
    start_time = time.time()

    password = get_password(provider["keychain_service"])
    client = IMAPClient(
        host=provider["host"],
        port=provider["port"],
        login=provider["login"],
        password=password,
    )

    invoices: List[Dict[str, Any]] = []
    total_scanned = 0
    invoice_folders: List[str] = []

    try:
        client.connect()

        # Discover invoice folders
        for prefix in SCAN_FOLDER_PREFIXES:
            found = client.list_folders(f"{prefix}/*")
            invoice_folders.extend(found)

        if invoice_folders:
            log.info(
                "Found %d invoice folders: %s",
                len(invoice_folders),
                ", ".join(invoice_folders),
            )
        else:
            log.warning(
                "No Factures/* or Financier/* folders found. "
                "Run 'organize' first to sort emails into folders."
            )

        for folder in invoice_folders:
            folder_invoices, folder_total = _scan_folder(
                client, folder, max_errors, log,
            )
            invoices.extend(folder_invoices)
            total_scanned += folder_total

    except Exception as e:
        log.error("Unexpected error during scan: %s", e)
    finally:
        client.disconnect()

    duration = round(time.time() - start_time, 1)

    report = build_report(account, invoices, total_scanned)
    json_path, txt_path = _write_reports(report, account)

    log.info("Reports written: %s, %s", json_path, txt_path)
    log.info(
        "=== INVOICE SCAN END === invoices=%d scanned=%d folders=%d duration=%ss",
        len(invoices), total_scanned, len(invoice_folders), duration,
    )

    # Print summary
    print(f"\n{'=' * 50}")
    print(f"  {account.upper()} — Scan des factures terminé")
    print(f"{'=' * 50}")
    print(f"  Courriels scannés : {total_scanned}")
    print(f"  Factures trouvées : {len(invoices)}")
    if invoice_folders:
        print(f"  Dossiers scannés  : {len(invoice_folders)} dossiers")
    else:
        print(f"  ⚠ Aucun dossier Factures/Financier trouvé — exécuter 'organize' d'abord")
    print()
    for prov_name in sorted(report["providers"].keys()):
        prov = report["providers"][prov_name]
        tag = "[PDF]" if prov["has_pdf_attachments"] else "[LIEN]" if prov.get("link_only") else "[?]"
        print(f"  {prov_name:<20s} {prov['count']} factures  {tag}")
    print(f"\n  Rapports : {json_path}")
    print(f"             {txt_path}")
    print(f"  Durée : {duration}s")

    return report
```

- [ ] **Step 2: Update test_invoice_scanner.py — remove is_invoice tests**

Replace `tests/test_invoice_scanner.py` with:

```python
"""Tests for invoice scanner — provider resolution, PDF extraction, report building."""

import unittest
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

from email_archiver.invoice_scanner import (
    resolve_provider, extract_pdf_info, build_report,
    _provider_from_folder,
)


class TestResolveProvider(unittest.TestCase):
    """Test provider name resolution from email addresses."""

    def test_known_provider_anthropic(self):
        self.assertEqual(resolve_provider("billing@anthropic.com"), "Anthropic")

    def test_known_provider_google(self):
        self.assertEqual(resolve_provider("payments-noreply@google.com"), "Google")

    def test_known_provider_xplore(self):
        self.assertEqual(resolve_provider("billing@xplore.ca"), "Xplore")

    def test_known_provider_staples(self):
        self.assertEqual(resolve_provider("orders@staples.ca"), "BureauEnGros")

    def test_known_provider_greengeeks(self):
        self.assertEqual(resolve_provider("billing@greengeeks.com"), "GreenGeeks")

    def test_known_provider_telus(self):
        self.assertEqual(resolve_provider("factures@telus.com"), "Telus")

    def test_known_provider_aquavoice(self):
        self.assertEqual(resolve_provider("billing@aquavoice.com"), "AquaVoice")

    def test_known_provider_fal(self):
        self.assertEqual(resolve_provider("billing@fal.ai"), "Fal")

    def test_unknown_provider_derives_from_domain(self):
        self.assertEqual(resolve_provider("billing@newservice.io"), "Newservice")

    def test_unknown_provider_complex_domain(self):
        self.assertEqual(resolve_provider("noreply@mail.bigcorp.com"), "Bigcorp")

    def test_unknown_provider_subdomain(self):
        self.assertEqual(resolve_provider("billing@e.company.org"), "Company")


class TestProviderFromFolder(unittest.TestCase):
    """Test folder-name-to-provider derivation."""

    def test_factures_folder(self):
        self.assertEqual(_provider_from_folder("Factures/Anthropic"), "Anthropic")

    def test_financier_folder(self):
        self.assertEqual(_provider_from_folder("Financier/Desjardins"), "Desjardins")

    def test_inbox_returns_none(self):
        self.assertIsNone(_provider_from_folder("INBOX"))

    def test_unknown_prefix_returns_none(self):
        self.assertIsNone(_provider_from_folder("Dev-Tech/GitHub"))


class TestExtractPdfInfo(unittest.TestCase):
    """Test PDF attachment detection from email.message.Message objects."""

    def _make_email_with_pdf(self, filename="invoice.pdf", pdf_content=b"%PDF-1.4 fake"):
        msg = MIMEMultipart()
        msg["From"] = "billing@anthropic.com"
        msg["Subject"] = "Your invoice"
        msg["Date"] = "Thu, 01 Apr 2026 10:00:00 +0000"

        body = MIMEText("Please find your invoice attached.", "plain")
        msg.attach(body)

        pdf = MIMEBase("application", "pdf")
        pdf.set_payload(pdf_content)
        encoders.encode_base64(pdf)
        pdf.add_header("Content-Disposition", "attachment", filename=filename)
        msg.attach(pdf)

        return msg

    def _make_email_no_attachment(self):
        msg = MIMEText("Your invoice is available at https://billing.example.com/inv/123")
        msg["From"] = "billing@example.com"
        msg["Subject"] = "Your invoice is ready"
        msg["Date"] = "Thu, 01 Apr 2026 10:00:00 +0000"
        return msg

    def test_email_with_pdf_detected(self):
        msg = self._make_email_with_pdf("invoice-march.pdf", b"%PDF" + b"\x00" * 100)
        info = extract_pdf_info(msg)
        self.assertTrue(info["has_pdf"])
        self.assertEqual(len(info["pdf_files"]), 1)
        self.assertEqual(info["pdf_files"][0]["filename"], "invoice-march.pdf")
        self.assertGreater(info["pdf_files"][0]["size_bytes"], 0)

    def test_email_without_pdf(self):
        msg = self._make_email_no_attachment()
        info = extract_pdf_info(msg)
        self.assertFalse(info["has_pdf"])
        self.assertEqual(len(info["pdf_files"]), 0)

    def test_email_with_multiple_pdfs(self):
        msg = MIMEMultipart()
        msg["From"] = "billing@company.com"
        msg["Subject"] = "Monthly invoices"
        msg["Date"] = "Thu, 01 Apr 2026 10:00:00 +0000"
        msg.attach(MIMEText("Two invoices attached."))

        for name in ["invoice-1.pdf", "invoice-2.pdf"]:
            pdf = MIMEBase("application", "pdf")
            pdf.set_payload(b"%PDF-fake-content")
            encoders.encode_base64(pdf)
            pdf.add_header("Content-Disposition", "attachment", filename=name)
            msg.attach(pdf)

        info = extract_pdf_info(msg)
        self.assertTrue(info["has_pdf"])
        self.assertEqual(len(info["pdf_files"]), 2)
        filenames = [f["filename"] for f in info["pdf_files"]]
        self.assertIn("invoice-1.pdf", filenames)
        self.assertIn("invoice-2.pdf", filenames)

    def test_link_only_detected(self):
        html_body = '<html><body><a href="https://billing.example.com/invoice/123">View invoice</a></body></html>'
        msg = MIMEText(html_body, "html")
        msg["From"] = "billing@example.com"
        msg["Subject"] = "Your invoice"
        msg["Date"] = "Thu, 01 Apr 2026 10:00:00 +0000"
        info = extract_pdf_info(msg)
        self.assertFalse(info["has_pdf"])
        self.assertTrue(info["link_only"])


class TestBuildReport(unittest.TestCase):
    """Test report generation from invoice scan data."""

    def test_report_structure(self):
        invoices = [
            {
                "uid": "4532",
                "from": "billing@anthropic.com",
                "provider": "Anthropic",
                "subject": "Your March invoice",
                "date": "2026-03-01",
                "has_pdf": True,
                "link_only": False,
                "pdf_files": [{"filename": "invoice.pdf", "size_bytes": 45230}],
            },
            {
                "uid": "4600",
                "from": "billing@anthropic.com",
                "provider": "Anthropic",
                "subject": "Your April invoice",
                "date": "2026-04-01",
                "has_pdf": True,
                "link_only": False,
                "pdf_files": [{"filename": "invoice.pdf", "size_bytes": 42100}],
            },
            {
                "uid": "5000",
                "from": "payments@google.com",
                "provider": "Google",
                "subject": "Google Workspace invoice",
                "date": "2026-03-15",
                "has_pdf": False,
                "link_only": True,
                "pdf_files": [],
            },
        ]

        report = build_report("gmail", invoices, total_scanned=1200)

        self.assertEqual(report["account"], "gmail")
        self.assertEqual(report["total_emails_scanned"], 1200)
        self.assertEqual(report["invoices_found"], 3)

        self.assertIn("Anthropic", report["providers"])
        self.assertEqual(report["providers"]["Anthropic"]["count"], 2)
        self.assertTrue(report["providers"]["Anthropic"]["has_pdf_attachments"])
        self.assertIn("2026-03", report["providers"]["Anthropic"]["months"])
        self.assertIn("2026-04", report["providers"]["Anthropic"]["months"])

        self.assertIn("Google", report["providers"])
        self.assertEqual(report["providers"]["Google"]["count"], 1)
        self.assertFalse(report["providers"]["Google"]["has_pdf_attachments"])
        self.assertTrue(report["providers"]["Google"]["link_only"])

        self.assertEqual(len(report["invoices"]), 3)

    def test_report_empty_invoices(self):
        report = build_report("gmail", [], total_scanned=500)
        self.assertEqual(report["invoices_found"], 0)
        self.assertEqual(report["providers"], {})
        self.assertEqual(report["invoices"], [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run full test suite**

Run: `/opt/homebrew/bin/python3.13 -m unittest discover -s tests -v`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add email_archiver/invoice_scanner.py tests/test_invoice_scanner.py
git commit -m "refactor: invoice scanner uses pre-classified folders only

Removed is_invoice(), INVOICE_FROM_PATTERNS, INVOICE_SUBJECT_STRINGS,
and _scan_inbox(). Scanner now only discovers and scans Factures/* and
Financier/* folders populated by organize."
```

---

### Task 5: Update cli.py — remove archive command

**Files:**
- Modify: `email_archiver/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Update cli.py — remove archive command**

Replace `email_archiver/cli.py` with:

```python
"""
CLI entry point for email-archiver.

Usage:
    python -m email_archiver organize gmail
    python -m email_archiver organize all
    python -m email_archiver preview gmail
    python -m email_archiver preview yahoo -n 20
    python -m email_archiver stats gmail
    python -m email_archiver invoices scan gmail
    python -m email_archiver invoices download gmail --month 2026-04
"""

import argparse
import sys

from email_archiver.archiver import run_preview, show_stats
from email_archiver.config import PROVIDERS
from email_archiver.invoice_downloader import run_download
from email_archiver.invoice_scanner import run_scan
from email_archiver.organizer import run_organize


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="email-archiver",
        description="IMAP email archiver for Gmail, iCloud, and Yahoo",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # organize
    p_organize = subparsers.add_parser(
        "organize", help="Sort inbox into folders + archive noise"
    )
    p_organize.add_argument(
        "account",
        choices=[*PROVIDERS.keys(), "all"],
        help="Account to organize (or 'all')",
    )

    # preview
    p_preview = subparsers.add_parser(
        "preview", help="Preview classification (read-only)"
    )
    p_preview.add_argument(
        "account",
        choices=list(PROVIDERS.keys()),
        help="Account to preview",
    )
    p_preview.add_argument(
        "-n", "--limit",
        type=int,
        default=100,
        help="Number of emails to preview (default: 100)",
    )

    # stats
    p_stats = subparsers.add_parser("stats", help="Show cumulative stats")
    p_stats.add_argument(
        "account",
        choices=[*PROVIDERS.keys(), "all"],
        help="Account to show stats for (or 'all')",
    )

    # invoices
    p_invoices = subparsers.add_parser(
        "invoices", help="Scan for invoices and download PDFs"
    )
    invoices_sub = p_invoices.add_subparsers(dest="action", required=True)

    # invoices scan
    p_inv_scan = invoices_sub.add_parser(
        "scan", help="Scan invoice folders (read-only)"
    )
    p_inv_scan.add_argument(
        "account",
        choices=list(PROVIDERS.keys()),
        help="Account to scan",
    )

    # invoices download
    p_inv_download = invoices_sub.add_parser(
        "download", help="Download invoice PDFs for a month"
    )
    p_inv_download.add_argument(
        "account",
        choices=list(PROVIDERS.keys()),
        help="Account to download from",
    )
    p_inv_download.add_argument(
        "--month",
        type=str,
        default=None,
        help="Target month as YYYY-MM (default: current month)",
    )

    args = parser.parse_args()

    if args.command == "organize":
        accounts = list(PROVIDERS.keys()) if args.account == "all" else [args.account]
        for acct in accounts:
            run_organize(acct)

    elif args.command == "preview":
        run_preview(args.account, limit=args.limit)

    elif args.command == "stats":
        accounts = list(PROVIDERS.keys()) if args.account == "all" else [args.account]
        for acct in accounts:
            show_stats(acct)

    elif args.command == "invoices":
        if args.action == "scan":
            run_scan(args.account)
        elif args.action == "download":
            run_download(args.account, month=args.month)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Update test_cli.py — add organize test, remove archive references**

Replace `tests/test_cli.py` with:

```python
"""Tests for CLI argument parsing."""

import unittest
from unittest.mock import patch, MagicMock

from email_archiver.cli import main


class TestOrganizeCLI(unittest.TestCase):
    """Test the organize subcommand argument parsing."""

    @patch("email_archiver.cli.run_organize")
    def test_organize_single_account(self, mock_organize):
        mock_organize.return_value = {"Factures/Anthropic": 5}
        with patch("sys.argv", ["email-archiver", "organize", "gmail"]):
            main()
        mock_organize.assert_called_once_with("gmail")

    @patch("email_archiver.cli.run_organize")
    def test_organize_all(self, mock_organize):
        mock_organize.return_value = {}
        with patch("sys.argv", ["email-archiver", "organize", "all"]):
            main()
        self.assertEqual(mock_organize.call_count, 3)  # gmail, icloud, yahoo


class TestPreviewCLI(unittest.TestCase):
    """Test the preview subcommand argument parsing."""

    @patch("email_archiver.cli.run_preview")
    def test_preview_default_limit(self, mock_preview):
        with patch("sys.argv", ["email-archiver", "preview", "gmail"]):
            main()
        mock_preview.assert_called_once_with("gmail", limit=100)

    @patch("email_archiver.cli.run_preview")
    def test_preview_custom_limit(self, mock_preview):
        with patch("sys.argv", ["email-archiver", "preview", "icloud", "-n", "20"]):
            main()
        mock_preview.assert_called_once_with("icloud", limit=20)


class TestInvoicesCLI(unittest.TestCase):
    """Test the invoices subcommand argument parsing."""

    @patch("email_archiver.cli.run_scan")
    def test_invoices_scan(self, mock_scan):
        mock_scan.return_value = {"invoices_found": 5}
        with patch("sys.argv", ["email-archiver", "invoices", "scan", "gmail"]):
            main()
        mock_scan.assert_called_once_with("gmail")

    @patch("email_archiver.cli.run_download")
    def test_invoices_download_with_month(self, mock_download):
        mock_download.return_value = {"downloaded": 3}
        with patch("sys.argv", ["email-archiver", "invoices", "download", "gmail", "--month", "2026-04"]):
            main()
        mock_download.assert_called_once_with("gmail", month="2026-04")

    @patch("email_archiver.cli.run_download")
    def test_invoices_download_default_month(self, mock_download):
        mock_download.return_value = {"downloaded": 0}
        with patch("sys.argv", ["email-archiver", "invoices", "download", "gmail"]):
            main()
        mock_download.assert_called_once_with("gmail", month=None)


class TestArchiveCommandRemoved(unittest.TestCase):
    """Verify that the old 'archive' command no longer exists."""

    def test_archive_command_rejected(self):
        with patch("sys.argv", ["email-archiver", "archive", "gmail"]):
            with self.assertRaises(SystemExit):
                main()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run full test suite**

Run: `/opt/homebrew/bin/python3.13 -m unittest discover -s tests -v`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add email_archiver/cli.py tests/test_cli.py
git commit -m "refactor: remove archive CLI command, organize does everything

The 'archive' subcommand is removed. 'organize' now handles both folder
sorting and noise archiving. Added CLI tests for organize and preview."
```

---

### Task 6: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update CLAUDE.md to reflect new architecture**

Apply these changes to `CLAUDE.md`:

1. In the **Commands** section, remove the `archive` commands and update descriptions:

```bash
# CLI commands
/opt/homebrew/bin/python3.13 -m email_archiver preview gmail        # read-only, show destinations
/opt/homebrew/bin/python3.13 -m email_archiver preview icloud -n 20 # read-only, 20 emails
/opt/homebrew/bin/python3.13 -m email_archiver organize gmail       # sort into folders + archive noise
/opt/homebrew/bin/python3.13 -m email_archiver organize icloud
/opt/homebrew/bin/python3.13 -m email_archiver stats all
/opt/homebrew/bin/python3.13 -m email_archiver invoices scan gmail    # scan Factures/Financier folders
/opt/homebrew/bin/python3.13 -m email_archiver invoices download gmail --month 2026-04  # download PDFs
```

2. In the **Architecture** section, update to:

```
`cli.py` → delegates to `archiver.py` (preview/stats), `organizer.py` (organize — sort + archive), `invoice_scanner.py` (invoices scan), or `invoice_downloader.py` (invoices download). All use `IMAPClient` (imap_client.py) for a single persistent IMAP connection, `classifier.py` for unified email classification, and `config.py` for provider configs + macOS Keychain credential retrieval.
```

3. In the **Classification** section, update to:

```
`classifier.py`: unified `classify(from, subject)` function. Returns folder name (e.g., "Factures/Anthropic"), `"_archive"` for noise, or `""` to keep in INBOX. ~150 from-address substring patterns + ~30 subject regex patterns. Specific sender patterns (steps 1–17) shadow generic noise patterns (step 18). Safe default — returns `""` (keep) if no pattern matches.
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for unified classifier architecture

Removed archive command references. Updated architecture and
classification sections to reflect the unified classify() function."
```

---

### Task 7: Final verification — run all tests

- [ ] **Step 1: Run the full test suite**

Run: `/opt/homebrew/bin/python3.13 -m unittest discover -s tests -v`
Expected: All tests pass, 0 errors, 0 failures

- [ ] **Step 2: Verify no import errors — import every module**

Run:
```bash
/opt/homebrew/bin/python3.13 -c "
from email_archiver.classifier import classify, should_archive, categorize
from email_archiver.archiver import run_preview, show_stats, save_stats
from email_archiver.organizer import run_organize
from email_archiver.invoice_scanner import run_scan, resolve_provider, extract_pdf_info
from email_archiver.invoice_downloader import run_download
from email_archiver.cli import main
print('All imports OK')
"
```
Expected: `All imports OK`

- [ ] **Step 3: Verify classify() covers old patterns — spot check**

Run:
```bash
/opt/homebrew/bin/python3.13 -c "
from email_archiver.classifier import classify

# Old classifier patterns that now go to named folders
assert classify('no-reply@coinbase.com', 'Trade') == 'Crypto'
assert classify('alerts@equifax.ca', 'Score') == 'Financier/Credit'
assert classify('noreply@linode.com', 'Alert') == 'Dev-Tech'
assert classify('info@vargacombat.com', 'Lesson') == 'Formations'

# Old classifier noise patterns still archived
assert classify('noreply@example.com', 'Hello') == '_archive'
assert classify('sender@x.com', 'Click to unsubscribe') == '_archive'

# Priority: specific wins over generic
assert classify('noreply@bnc.ca', 'Alerte') == 'Financier/BNC'
assert classify('nepasrepondre@desjardins.com', 'Relevé') == 'Financier/Desjardins'

# Safe default
assert classify('unknown@random.org', 'Hello') == ''

print('All spot checks passed')
"
```
Expected: `All spot checks passed`

- [ ] **Step 4: Verify old run_archive is gone**

Run:
```bash
/opt/homebrew/bin/python3.13 -c "
from email_archiver import archiver
assert not hasattr(archiver, 'run_archive'), 'run_archive should be removed'
print('run_archive confirmed removed')
"
```
Expected: `run_archive confirmed removed`

- [ ] **Step 5: Verify old is_invoice is gone**

Run:
```bash
/opt/homebrew/bin/python3.13 -c "
from email_archiver import invoice_scanner
assert not hasattr(invoice_scanner, 'is_invoice'), 'is_invoice should be removed'
print('is_invoice confirmed removed')
"
```
Expected: `is_invoice confirmed removed`
