"""Tests for email classifier patterns."""

import unittest

from email_archiver.classifier import should_archive


class TestFromPatterns(unittest.TestCase):
    """Test from-address pattern matching."""

    def test_noreply(self):
        self.assertTrue(should_archive("noreply@example.com", "Hello"))

    def test_no_reply_dash(self):
        self.assertTrue(should_archive("no-reply@company.com", "Update"))

    def test_newsletter(self):
        self.assertTrue(should_archive("newsletter@news.com", "Weekly digest"))

    def test_notification(self):
        self.assertTrue(should_archive("notification@service.com", "Alert"))

    def test_marketing(self):
        self.assertTrue(should_archive("marketing@brand.com", "New products"))

    def test_nepasrepondre(self):
        self.assertTrue(should_archive("nepasrepondre@desjardins.com", "Relevé"))

    def test_bulk_subdomain_email(self):
        self.assertTrue(should_archive("promo@email.company.com", "Sale"))

    def test_bulk_subdomain_e(self):
        self.assertTrue(should_archive("news@e.company.com", "Updates"))

    def test_facebookmail(self):
        self.assertTrue(should_archive("notification@facebookmail.com", "Activity"))

    def test_patreon(self):
        self.assertTrue(should_archive("hello@patreon.com", "New post"))

    def test_coinbase(self):
        self.assertTrue(should_archive("no-reply@coinbase.com", "Transaction"))

    def test_linode(self):
        self.assertTrue(should_archive("noreply@linode.com", "Device alert"))

    def test_equifax(self):
        self.assertTrue(should_archive("alerts@equifax.ca", "Score update"))

    def test_coupa(self):
        self.assertTrue(should_archive("noreply@coupa.com", "PO update"))

    def test_personal_email_kept(self):
        """Personal emails must NOT be archived."""
        self.assertFalse(should_archive("mom@gmail.com", "Dinner tonight?"))

    def test_work_email_kept(self):
        self.assertFalse(should_archive("boss@company.com", "Meeting at 3pm"))

    def test_friend_kept(self):
        self.assertFalse(should_archive("pascal@hotmail.com", "Hey!"))


class TestSubjectPatterns(unittest.TestCase):
    """Test subject pattern matching."""

    def test_unsubscribe(self):
        self.assertTrue(should_archive("sender@x.com", "Click to unsubscribe"))

    def test_your_order(self):
        self.assertTrue(should_archive("shop@x.com", "Your order has shipped"))

    def test_password_reset(self):
        self.assertTrue(should_archive("auth@x.com", "Password reset request"))

    def test_newsletter_subject(self):
        self.assertTrue(should_archive("sender@x.com", "Weekly newsletter"))

    def test_save_percent(self):
        self.assertTrue(should_archive("shop@x.com", "Save 50% today only"))

    def test_limited_time(self):
        self.assertTrue(should_archive("promo@x.com", "Limited time offer!"))

    def test_security_alert(self):
        self.assertTrue(should_archive("security@x.com", "Security alert for your account"))

    def test_french_offre(self):
        self.assertTrue(should_archive("promo@x.com", "Offre spéciale du jour"))

    def test_french_rabais(self):
        self.assertTrue(should_archive("shop@x.com", "Rabais de 30%"))

    def test_french_infolettre(self):
        self.assertTrue(should_archive("news@x.com", "Infolettre de mars"))

    def test_mot_de_passe(self):
        self.assertTrue(should_archive("auth@x.com", "Votre mot de passe"))

    def test_podcast(self):
        self.assertTrue(should_archive("pod@x.com", "New podcast episode"))

    def test_normal_subject_kept(self):
        """Normal conversation subjects must NOT be archived."""
        self.assertFalse(should_archive("friend@x.com", "Can we meet tomorrow?"))

    def test_work_subject_kept(self):
        self.assertFalse(should_archive("coworker@x.com", "Q2 report review"))

    def test_empty_kept(self):
        """Empty from/subject should be kept (safe default)."""
        self.assertFalse(should_archive("", ""))


class TestSafeDefault(unittest.TestCase):
    """Verify safe default: ambiguous emails are KEPT, not archived."""

    def test_unknown_sender_neutral_subject(self):
        self.assertFalse(should_archive("unknown@random.org", "Hello there"))

    def test_partial_match_not_enough(self):
        # "info" appears in "information" but pattern is "info@"
        self.assertFalse(should_archive("information-desk@company.com", "Inquiry"))


if __name__ == "__main__":
    unittest.main()
