"""
Comprehensive tests for the unified classify() function and legacy wrappers.

Test classes:
- TestClassifyNamedFolders  — specific senders map to correct named folders
- TestClassifyArchive       — noise patterns produce _archive
- TestClassifyKeep          — unrecognized emails return "" (safe default)
- TestClassifyPriority      — specific senders shadow generic noise
- TestLegacyWrappers        — should_archive() and categorize() compatibility
"""

import unittest

from email_archiver.classifier import classify, should_archive, categorize


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _c(from_addr: str, subject: str = "Hello") -> str:
    """Shorthand: call classify() with a subject default."""
    return classify(from_addr, subject)


# ---------------------------------------------------------------------------
class TestClassifyNamedFolders(unittest.TestCase):
    """Specific senders must map to correct named folders."""

    # --- Self-sent ---
    def test_self_sent_justinlacerte(self):
        self.assertEqual(_c("justinlacerte@gmail.com"), "Notes-personnelles")

    def test_self_sent_jlacerte(self):
        self.assertEqual(_c("jlacerte@solutionsjl.ca"), "Notes-personnelles")

    # --- Travail ---
    def test_travail_deslauriers(self):
        self.assertEqual(_c("info@deslauriers1975.ca"), "Travail/Deslauriers")

    def test_travail_gidar(self):
        self.assertEqual(_c("admin@gi-dar.ca"), "Travail/GI-DAR")

    def test_travail_acq(self):
        self.assertEqual(_c("contact@acq.org"), "Travail/ACQ")

    def test_travail_apchq(self):
        self.assertEqual(_c("communication@apchq.com"), "Travail/APCHQ")

    def test_travail_cfcpc(self):
        self.assertEqual(_c("info@cfcpc.ca"), "Travail/APCHQ")

    def test_travail_gatineau(self):
        self.assertEqual(_c("permit@gatineau.ca"), "Travail/Gatineau")

    def test_travail_sqi(self):
        self.assertEqual(_c("noreply@sqi.gouv.qc.ca"), "Travail/SQI")

    def test_travail_ssss(self):
        self.assertEqual(_c("noreply@ssss.gouv.qc.ca"), "Travail/CISSSO")

    def test_travail_mecg(self):
        self.assertEqual(_c("pascal@mecg.ca"), "Travail/MECG")

    def test_travail_alarmegs(self):
        self.assertEqual(_c("service@alarmegs.ca"), "Travail/AlarmeGS")

    def test_travail_congresgatineau(self):
        self.assertEqual(_c("info@congresgatineau.com"), "Travail/PalaisCongres")

    def test_travail_fournisseurs_coupa(self):
        self.assertEqual(_c("supplier@coupa.com"), "Travail/Fournisseurs")

    def test_travail_clients_realstar(self):
        self.assertEqual(_c("billing@realstar.ca"), "Travail/Clients")

    # --- Gouvernement ---
    def test_gouvernement_cnesst(self):
        self.assertEqual(_c("info@cnesst.gouv.qc.ca"), "Gouvernement/CNESST")

    def test_gouvernement_mapaq(self):
        self.assertEqual(_c("noreply@mapaq.gouv.qc.ca"), "Gouvernement/MAPAQ")

    def test_gouvernement_mrcpapineau(self):
        self.assertEqual(_c("info@mrcpapineau.com"), "Gouvernement/MRC-Papineau")

    def test_gouvernement_cldpapineau(self):
        self.assertEqual(_c("info@cldpapineau.ca"), "Gouvernement/CLD-Papineau")

    # --- Agriculture ---
    def test_agriculture_upa(self):
        self.assertEqual(_c("info@upa.qc.ca"), "Agriculture/UPA")

    def test_agriculture_pbq(self):
        self.assertEqual(_c("pbq@agr.gouv.qc.ca"), "Agriculture/UPA")

    def test_agriculture_fadq(self):
        self.assertEqual(_c("info@fadq.qc.ca"), "Agriculture/FADQ")

    # --- Financier ---
    def test_financier_desjardins(self):
        self.assertEqual(_c("nepasrepondre@desjardins.com"), "Financier/Desjardins")

    def test_financier_bnc(self):
        self.assertEqual(_c("noreply@bnc.ca"), "Financier/BNC")

    def test_financier_interac(self):
        self.assertEqual(_c("noreply@interac.ca"), "Financier/Interac")

    def test_financier_paypal(self):
        self.assertEqual(_c("service@paypal.com"), "Financier/PayPal")

    def test_financier_revenuquebec(self):
        self.assertEqual(_c("info@revenuquebec.ca"), "Financier/RevenuQC")

    def test_financier_servicesquebec(self):
        self.assertEqual(_c("info@servicesquebec.gouv.qc.ca"), "Financier/RevenuQC")

    def test_financier_hydro(self):
        self.assertEqual(_c("info@hydroquebec.com"), "Financier/Hydro-Quebec")

    def test_financier_caa(self):
        self.assertEqual(_c("info@caaquebec.com"), "Financier/CAA")

    def test_financier_equifax(self):
        self.assertEqual(_c("alerts@equifax.ca"), "Financier/Credit")

    def test_financier_creditkarma(self):
        self.assertEqual(_c("noreply@creditkarma.com"), "Financier/Credit")

    def test_financier_transunion(self):
        self.assertEqual(_c("alerts@transunion.ca"), "Financier/Credit")

    def test_financier_fondsftq(self):
        self.assertEqual(_c("info@fondsftq.com"), "Financier/FondsFTQ")

    # --- Assurance ---
    def test_assurance_charlebois(self):
        self.assertEqual(_c("info@charleboistrepanier.com"), "Assurance/Charlebois")

    def test_assurance_turquoise(self):
        self.assertEqual(_c("info@laturquoise.ca"), "Assurance/Turquoise")

    def test_assurance_bfl(self):
        self.assertEqual(_c("info@bflcanada.ca"), "Assurance/BFL")

    def test_assurance_intact(self):
        self.assertEqual(_c("info@intact.ca"), "Assurance")

    def test_assurance_promutuel(self):
        self.assertEqual(_c("info@promutuel.ca"), "Assurance")

    def test_assurance_inalco(self):
        self.assertEqual(_c("contact@inalco.ca"), "Assurance")

    # --- Comptabilite ---
    def test_comptabilite_falardeau(self):
        self.assertEqual(_c("cpa@falardeau.ca"), "Comptabilite")

    def test_comptabilite_scfconseils(self):
        self.assertEqual(_c("info@scfconseils.ca"), "Comptabilite")

    def test_comptabilite_fcoulombe(self):
        self.assertEqual(_c("fcoulombe@apoint.ca"), "Comptabilite")

    def test_comptabilite_dbadea(self):
        self.assertEqual(_c("dbadea@example.ca"), "Comptabilite")

    # --- Education ---
    def test_education_cscv(self):
        self.assertEqual(_c("info@cscv.qc.ca"), "Education")

    def test_education_csdraveurs(self):
        self.assertEqual(_c("noreply@csdraveurs.qc.ca"), "Education")

    def test_education_cssd(self):
        self.assertEqual(_c("info@cssd.gouv.qc.ca"), "Education")

    # --- Personnel ---
    def test_personnel_famille_melokiii(self):
        self.assertEqual(_c("melokiii@hotmail.com"), "Personnel/Famille")

    def test_personnel_famille_coutoumelodie(self):
        self.assertEqual(_c("coutoumelodie@gmail.com"), "Personnel/Famille")

    def test_personnel_famille_jomaev(self):
        self.assertEqual(_c("jomaev@example.com"), "Personnel/Famille")

    def test_personnel_famille_cpemillecouleurs(self):
        self.assertEqual(_c("admin@cpemillecouleurs.ca"), "Personnel/Famille")

    def test_personnel_famille_morgane(self):
        self.assertEqual(_c("morgane@example.com"), "Personnel/Famille")

    def test_personnel_dominique(self):
        self.assertEqual(_c("info@cafelabrulerie.com"), "Personnel/Dominique")

    def test_personnel_sante(self):
        self.assertEqual(_c("rdv@orthodontiste.ca"), "Personnel/Sante")

    def test_personnel_fitness(self):
        self.assertEqual(_c("noreply@mapmyrun.com"), "Personnel/Fitness")

    def test_personnel_coaching(self):
        self.assertEqual(_c("maudeperron@gmail.com"), "Personnel/Coaching")

    # --- Factures ---
    def test_factures_anthropic(self):
        self.assertEqual(_c("billing@anthropic.com"), "Factures/Anthropic")

    def test_factures_google_payment(self):
        self.assertEqual(_c("payment-noreply@google.com"), "Factures/Google")

    def test_factures_google_invoice(self):
        self.assertEqual(_c("invoice@google.com"), "Factures/Google")

    def test_factures_google_workspace(self):
        self.assertEqual(_c("workspace@google.com"), "Factures/Google")

    def test_factures_aquavoice(self):
        self.assertEqual(_c("billing@aquavoice.com"), "Factures/AquaVoice")

    def test_factures_fal(self):
        self.assertEqual(_c("billing@fal.ai"), "Factures/fal")

    def test_factures_xplore(self):
        self.assertEqual(_c("noreply@xplore.ca"), "Factures/Xplore")

    def test_factures_staples(self):
        self.assertEqual(_c("orders@staples.ca"), "Factures/BureauEnGros")

    def test_factures_greengeeks(self):
        self.assertEqual(_c("billing@greengeeks.com"), "Factures/GreenGeeks")

    def test_factures_telus(self):
        self.assertEqual(_c("noreply@telus.com"), "Factures/Telus")

    # --- Dev-Tech ---
    def test_devtech_google_cloud(self):
        self.assertEqual(_c("cloudplatform-noreply@google.com"), "Dev-Tech/Google-Cloud")

    def test_devtech_netlify(self):
        self.assertEqual(_c("noreply@netlify.com"), "Dev-Tech/Netlify")

    def test_devtech_docker(self):
        self.assertEqual(_c("info@docker.com"), "Dev-Tech/Docker")

    def test_devtech_github(self):
        self.assertEqual(_c("noreply@github.com"), "Dev-Tech/GitHub")

    def test_devtech_ollama(self):
        self.assertEqual(_c("hello@ollama.com"), "Dev-Tech/Ollama")

    def test_devtech_claude(self):
        self.assertEqual(_c("noreply@claude.ai"), "Dev-Tech/Claude")

    def test_devtech_claude_com(self):
        self.assertEqual(_c("noreply@claude.com"), "Dev-Tech/Claude")

    def test_devtech_dynamous(self):
        self.assertEqual(_c("info@circle.so"), "Dev-Tech/Dynamous")

    def test_devtech_twilio(self):
        self.assertEqual(_c("hello@twilio.com"), "Dev-Tech/Twilio")

    def test_devtech_openai(self):
        self.assertEqual(_c("noreply@openai.com"), "Dev-Tech/OpenAI")

    def test_devtech_domaines_enom(self):
        self.assertEqual(_c("billing@enom.com"), "Dev-Tech/Domaines")

    def test_devtech_domaines_name_services(self):
        self.assertEqual(_c("noreply@name-services.com"), "Dev-Tech/Domaines")

    def test_devtech_bulk_cursor(self):
        self.assertEqual(_c("noreply@cursor.sh"), "Dev-Tech")

    def test_devtech_bulk_supabase(self):
        self.assertEqual(_c("noreply@supabase.io"), "Dev-Tech")

    def test_devtech_aws_noreply(self):
        self.assertEqual(_c("no-reply@amazon.com"), "Dev-Tech")

    def test_devtech_aws(self):
        self.assertEqual(_c("aws-marketing@email.amazon.com"), "Dev-Tech")

    # --- Formations ---
    def test_formations_vargacombat(self):
        self.assertEqual(_c("info@vargacombat.com"), "Formations")

    def test_formations_howtofightnow(self):
        self.assertEqual(_c("hello@howtofightnow.com"), "Formations")

    # --- Social ---
    def test_social_twitter(self):
        self.assertEqual(_c("info@twitter.com"), "Social")

    def test_social_linkedin(self):
        self.assertEqual(_c("noreply@linkedin.com"), "Social")

    def test_social_meta(self):
        self.assertEqual(_c("noreply@meta.com"), "Social")

    def test_social_facebook(self):
        self.assertEqual(_c("notification@facebookmail.com"), "Social")

    # --- Crypto ---
    def test_crypto_coinbase(self):
        self.assertEqual(_c("noreply@coinbase.com"), "Crypto")

    def test_crypto_netcoins(self):
        self.assertEqual(_c("noreply@netcoins.ca"), "Crypto")

    def test_crypto_gonetcoins(self):
        self.assertEqual(_c("info@gonetcoins.com"), "Crypto")

    # --- Newsletters ---
    def test_newsletters_quebecloisirs(self):
        self.assertEqual(_c("info@quebecloisirs.com"), "Newsletters")

    def test_newsletters_eff(self):
        self.assertEqual(_c("info@eff.org"), "Newsletters")

    def test_newsletters_drolementinspirant(self):
        self.assertEqual(_c("hello@drolementinspirant.com"), "Newsletters")

    def test_newsletters_shinybud(self):
        self.assertEqual(_c("loyalty@shinybud.com"), "Newsletters")

    def test_newsletters_renaudbray(self):
        self.assertEqual(_c("infolettre@renaud-bray.com"), "Newsletters")

    def test_newsletters_tommorrison(self):
        self.assertEqual(_c("info@tommorrison.uk"), "Newsletters")

    def test_newsletters_acces_credit(self):
        self.assertEqual(_c("info@acces-credit.ca"), "Newsletters")

    def test_newsletters_pentoncem(self):
        self.assertEqual(_c("news@info.pentoncem.com"), "Newsletters")

    def test_newsletters_tdworld(self):
        self.assertEqual(_c("editors@tdworld.com"), "Newsletters")

    def test_newsletters_logojoy(self):
        self.assertEqual(_c("hello@logojoy.com"), "Newsletters")

    def test_newsletters_intercom_mail(self):
        self.assertEqual(_c("hello@intercom-mail.com"), "Newsletters")

    def test_newsletters_centraideoutaouais(self):
        self.assertEqual(_c("info@centraideoutaouais.ca"), "Newsletters")

    def test_newsletters_leger360(self):
        self.assertEqual(_c("noreply@leger360.com"), "Newsletters")

    def test_newsletters_legerweb(self):
        self.assertEqual(_c("info@legerweb.com"), "Newsletters")

    def test_newsletters_surveygizmo(self):
        self.assertEqual(_c("noreply@surveygizmo.com"), "Newsletters")

    def test_newsletters_coursera(self):
        self.assertEqual(_c("info@coursera.org"), "Newsletters")

    def test_newsletters_umd(self):
        self.assertEqual(_c("info@umd.edu"), "Newsletters")

    def test_newsletters_ultimate_guitar(self):
        self.assertEqual(_c("noreply@ultimate-guitar.com"), "Newsletters")

    def test_newsletters_patreon(self):
        self.assertEqual(_c("hello@patreon.com"), "Newsletters")

    # --- Notifications ---
    def test_notifications_youtube(self):
        self.assertEqual(_c("noreply@youtube.com"), "Notifications/YouTube")

    def test_notifications_google(self):
        self.assertEqual(_c("noreply@accounts.google.com"), "Notifications/Google")

    def test_notifications_apple(self):
        self.assertEqual(_c("noreply@apple.com"), "Notifications/Apple")

    def test_notifications_itunes(self):
        self.assertEqual(_c("noreply@itunes.com"), "Notifications/Apple")

    def test_notifications_yahoo(self):
        self.assertEqual(_c("noreply@yahoo.com"), "Notifications")

    def test_notifications_postmaster(self):
        self.assertEqual(_c("postmaster@mail.example.com"), "Notifications")

    # --- Spam ---
    def test_spam_icloud_relay(self):
        self.assertEqual(_c("user_at_example.com@icloud.com"), "Spam")


# ---------------------------------------------------------------------------
class TestClassifyArchive(unittest.TestCase):
    """Noise patterns must produce _archive."""

    # Generic from-address noise
    def test_archive_noreply_generic(self):
        self.assertEqual(_c("noreply@somecompany.com"), "_archive")

    def test_archive_no_reply_dash(self):
        self.assertEqual(_c("no-reply@somecompany.com"), "_archive")

    def test_archive_notification_generic(self):
        self.assertEqual(_c("notification@unknownservice.com"), "_archive")

    def test_archive_newsletter_at(self):
        self.assertEqual(_c("newsletter@news.com"), "_archive")

    def test_archive_marketing_at(self):
        self.assertEqual(_c("marketing@brand.com"), "_archive")

    def test_archive_promo_at(self):
        self.assertEqual(_c("promo@deals.com"), "_archive")

    def test_archive_donotreply(self):
        self.assertEqual(_c("donotreply@service.com"), "_archive")

    def test_archive_mailer_daemon(self):
        self.assertEqual(_c("mailer-daemon@example.com"), "_archive")

    def test_archive_bounce(self):
        self.assertEqual(_c("bounce@mail.example.com"), "_archive")

    def test_archive_news_at(self):
        self.assertEqual(_c("news@updates.com"), "_archive")

    def test_archive_info_at(self):
        self.assertEqual(_c("info@randomcompany.com"), "_archive")

    def test_archive_nepasrepondre(self):
        self.assertEqual(_c("nepasrepondre@somebank.com"), "_archive")

    def test_archive_ne_pas_repondre(self):
        self.assertEqual(_c("ne-pas-repondre@service.ca"), "_archive")

    def test_archive_bulk_subdomain_e(self):
        self.assertEqual(_c("promo@e.company.com"), "_archive")

    def test_archive_bulk_subdomain_email(self):
        self.assertEqual(_c("news@email.company.com"), "_archive")

    def test_archive_bulk_subdomain_mail(self):
        self.assertEqual(_c("news@mail.company.com"), "_archive")

    def test_archive_bulk_subdomain_newsletter(self):
        self.assertEqual(_c("send@newsletter.company.com"), "_archive")

    def test_archive_canadiantire(self):
        self.assertEqual(_c("deals@canadiantire.ca"), "_archive")

    def test_archive_triangle(self):
        self.assertEqual(_c("points@triangle.com"), "_archive")

    def test_archive_cooperativeplacedumarche(self):
        self.assertEqual(_c("info@cooperativeplacedumarche.ca"), "_archive")

    def test_archive_chefsplate(self):
        self.assertEqual(_c("hello@chefsplate.com"), "_archive")

    def test_archive_clubcage(self):
        self.assertEqual(_c("promo@clubcage.ca"), "_archive")

    def test_archive_opinion_panalyticsgroup(self):
        self.assertEqual(_c("survey@opinion.panalyticsgroup.com"), "_archive")

    def test_archive_mail_corpo_ia(self):
        self.assertEqual(_c("news@mail-corpo.ia.ca"), "_archive")

    def test_archive_cegep_heritage(self):
        self.assertEqual(_c("info@cegep-heritage.qc.ca"), "_archive")

    def test_archive_privaterelay_appleid(self):
        self.assertEqual(_c("random@privaterelay.appleid.com"), "_archive")

    # Subject-based noise (from a neutral sender)
    def test_archive_subject_unsubscribe(self):
        self.assertEqual(classify("friend@example.com", "Click to unsubscribe"), "_archive")

    def test_archive_subject_your_order(self):
        self.assertEqual(classify("shop@example.com", "Your order has shipped"), "_archive")

    def test_archive_subject_your_receipt(self):
        self.assertEqual(classify("store@example.com", "Your receipt is ready"), "_archive")

    def test_archive_subject_shipping(self):
        self.assertEqual(classify("courier@example.com", "Shipping update"), "_archive")

    def test_archive_subject_password_reset(self):
        self.assertEqual(classify("auth@example.com", "Password reset request"), "_archive")

    def test_archive_subject_newsletter(self):
        self.assertEqual(classify("sender@example.com", "Weekly newsletter"), "_archive")

    def test_archive_subject_save_percent(self):
        self.assertEqual(classify("shop@example.com", "Save 50% today only"), "_archive")

    def test_archive_subject_limited_time(self):
        self.assertEqual(classify("deals@example.com", "Limited time offer!"), "_archive")

    def test_archive_subject_security_alert(self):
        self.assertEqual(classify("security@example.com", "Security alert for your account"), "_archive")

    def test_archive_subject_french_offre(self):
        self.assertEqual(classify("promo@example.com", "Offre spéciale du jour"), "_archive")

    def test_archive_subject_french_rabais(self):
        self.assertEqual(classify("deals@example.com", "Rabais de 30%"), "_archive")

    def test_archive_subject_infolettre(self):
        self.assertEqual(classify("news@example.com", "Infolettre de mars"), "_archive")

    def test_archive_subject_mot_de_passe(self):
        self.assertEqual(classify("auth@example.com", "Votre mot de passe temporaire"), "_archive")

    def test_archive_subject_podcast(self):
        self.assertEqual(classify("pod@example.com", "New podcast episode 42"), "_archive")

    def test_archive_subject_alerte_pointage(self):
        self.assertEqual(classify("bank@example.com", "Alerte pointage de crédit"), "_archive")


# ---------------------------------------------------------------------------
class TestClassifyKeep(unittest.TestCase):
    """Unrecognized emails must return '' (safe default — stay in INBOX)."""

    def test_keep_personal_email(self):
        self.assertEqual(_c("mom@gmail.com", "Dinner tonight?"), "")

    def test_keep_work_colleague(self):
        self.assertEqual(_c("boss@somecompany.com", "Meeting at 3pm"), "")

    def test_keep_friend_hotmail(self):
        self.assertEqual(_c("pascal@hotmail.com", "Hey!"), "")

    def test_keep_unknown_neutral(self):
        self.assertEqual(_c("unknown@random.org", "Hello there"), "")

    def test_keep_empty_from_and_subject(self):
        self.assertEqual(classify("", ""), "")

    def test_keep_normal_subject(self):
        self.assertEqual(_c("coworker@company.com", "Q2 report review"), "")

    def test_keep_info_in_email_username_not_at(self):
        # "info@" pattern uses substring "info@" — this should NOT match
        # because "information" doesn't contain "info@"
        self.assertEqual(_c("information-desk@company.com", "Inquiry"), "")


# ---------------------------------------------------------------------------
class TestClassifyPriority(unittest.TestCase):
    """Specific sender patterns must shadow generic noise (priority ordering)."""

    def test_bnc_not_archive(self):
        """noreply@bnc.ca → Financier/BNC, NOT _archive."""
        self.assertEqual(_c("noreply@bnc.ca"), "Financier/BNC")

    def test_desjardins_nepasrepondre(self):
        """nepasrepondre@desjardins.com → Financier/Desjardins, NOT _archive."""
        self.assertEqual(_c("nepasrepondre@desjardins.com"), "Financier/Desjardins")

    def test_interac_noreply(self):
        """noreply@interac.ca → Financier/Interac, NOT _archive."""
        self.assertEqual(_c("noreply@interac.ca"), "Financier/Interac")

    def test_mapaq_noreply(self):
        """noreply@mapaq.gouv.qc.ca → Gouvernement/MAPAQ, NOT _archive."""
        self.assertEqual(_c("noreply@mapaq.gouv.qc.ca"), "Gouvernement/MAPAQ")

    def test_cnesst_noreply(self):
        """notification@cnesst.gouv.qc.ca → Gouvernement/CNESST, NOT _archive."""
        self.assertEqual(_c("notification@cnesst.gouv.qc.ca"), "Gouvernement/CNESST")

    def test_github_noreply(self):
        """noreply@github.com → Dev-Tech/GitHub, NOT _archive."""
        self.assertEqual(_c("noreply@github.com"), "Dev-Tech/GitHub")

    def test_netlify_noreply(self):
        """noreply@netlify.com → Dev-Tech/Netlify, NOT _archive."""
        self.assertEqual(_c("noreply@netlify.com"), "Dev-Tech/Netlify")

    def test_youtube_noreply(self):
        """noreply@youtube.com → Notifications/YouTube, NOT _archive."""
        self.assertEqual(_c("noreply@youtube.com"), "Notifications/YouTube")

    def test_equifax_not_generic_archive(self):
        """alerts@equifax.ca → Financier/Credit (specific rule), not generic _archive."""
        self.assertEqual(_c("alerts@equifax.ca"), "Financier/Credit")

    def test_sqi_noreply(self):
        """noreply@sqi.gouv.qc.ca → Travail/SQI, NOT _archive."""
        self.assertEqual(_c("noreply@sqi.gouv.qc.ca"), "Travail/SQI")

    def test_coinbase_specific_folder(self):
        """noreply@coinbase.com → Crypto, NOT _archive."""
        self.assertEqual(_c("noreply@coinbase.com"), "Crypto")

    def test_mapmyrun_specific_folder(self):
        """noreply@mapmyrun.com → Personnel/Fitness, NOT _archive."""
        self.assertEqual(_c("noreply@mapmyrun.com"), "Personnel/Fitness")


# ---------------------------------------------------------------------------
class TestLegacyWrappers(unittest.TestCase):
    """should_archive() and categorize() must maintain backward compatibility."""

    # --- should_archive() ---
    def test_should_archive_noise_true(self):
        """Generic noise from-address → True."""
        self.assertTrue(should_archive("noreply@somecompany.com", "Hello"))

    def test_should_archive_noise_subject_true(self):
        """Noise subject → True."""
        self.assertTrue(should_archive("friend@example.com", "Save 30% today only"))

    def test_should_archive_named_folder_false(self):
        """Named folder (Financier/BNC) → False (it is NOT _archive)."""
        self.assertFalse(should_archive("noreply@bnc.ca", "Relevé"))

    def test_should_archive_keep_false(self):
        """Unrecognized email → False."""
        self.assertFalse(should_archive("boss@company.com", "Meeting"))

    def test_should_archive_safe_default_empty(self):
        """Empty from/subject → False."""
        self.assertFalse(should_archive("", ""))

    # --- categorize() ---
    def test_categorize_named_folder_returned(self):
        """Named folder → returned as-is."""
        self.assertEqual(categorize("noreply@bnc.ca", "Relevé"), "Financier/BNC")

    def test_categorize_archive_returns_empty(self):
        """_archive result → returned as '' (caller reads '' as leave-in-inbox)."""
        self.assertEqual(categorize("noreply@somecompany.com", "Hello"), "")

    def test_categorize_keep_returns_empty(self):
        """Unrecognized → ''."""
        self.assertEqual(categorize("boss@company.com", "Meeting"), "")

    def test_categorize_self_sent(self):
        self.assertEqual(categorize("justinlacerte@gmail.com", "Note"), "Notes-personnelles")

    def test_categorize_travail(self):
        self.assertEqual(categorize("info@deslauriers1975.ca", "PO"), "Travail/Deslauriers")

    def test_categorize_gouvernement(self):
        self.assertEqual(categorize("info@cnesst.gouv.qc.ca", "Dossier"), "Gouvernement/CNESST")


if __name__ == "__main__":
    unittest.main()
