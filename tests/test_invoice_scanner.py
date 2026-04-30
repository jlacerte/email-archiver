"""Tests for invoice scanner — classification, provider resolution, report building."""

import unittest

from email_archiver.invoice_scanner import is_invoice, resolve_provider


class TestIsInvoice(unittest.TestCase):
    """Test invoice detection patterns."""

    # --- From-address matches ---

    def test_anthropic_billing(self):
        self.assertTrue(is_invoice("billing@anthropic.com", "Your March invoice"))

    def test_xplore_billing(self):
        self.assertTrue(is_invoice("billing@xplore.ca", "Your bill is ready"))

    def test_google_payments(self):
        self.assertTrue(is_invoice("payments-noreply@google.com", "Google Workspace"))

    def test_greengeeks(self):
        self.assertTrue(is_invoice("billing@greengeeks.com", "Hosting renewal"))

    def test_telus(self):
        self.assertTrue(is_invoice("factures@telus.com", "Votre facture"))

    def test_staples(self):
        self.assertTrue(is_invoice("orders@staples.ca", "Order confirmation"))

    def test_aquavoice(self):
        self.assertTrue(is_invoice("billing@aquavoice.com", "Payment receipt"))

    def test_fal_ai(self):
        self.assertTrue(is_invoice("billing@fal.ai", "Monthly usage"))

    # --- Subject matches ---

    def test_subject_invoice(self):
        self.assertTrue(is_invoice("unknown@company.com", "Your invoice for March"))

    def test_subject_facture(self):
        self.assertTrue(is_invoice("unknown@company.com", "Votre facture mensuelle"))

    def test_subject_receipt(self):
        self.assertTrue(is_invoice("unknown@company.com", "Your receipt #12345"))

    def test_subject_recu(self):
        self.assertTrue(is_invoice("unknown@company.com", "Reçu de paiement"))

    def test_subject_billing(self):
        self.assertTrue(is_invoice("unknown@company.com", "Billing statement"))

    def test_subject_payment(self):
        self.assertTrue(is_invoice("unknown@company.com", "Payment confirmation"))

    def test_subject_your_bill(self):
        self.assertTrue(is_invoice("unknown@company.com", "Your bill is ready"))

    def test_subject_releve(self):
        self.assertTrue(is_invoice("unknown@company.com", "Votre relevé de compte"))

    def test_subject_statement(self):
        self.assertTrue(is_invoice("unknown@company.com", "Monthly statement"))

    def test_subject_order_confirmation(self):
        self.assertTrue(is_invoice("unknown@company.com", "Order confirmation #789"))

    # --- Non-matches (safe default: keep) ---

    def test_personal_email_not_invoice(self):
        self.assertFalse(is_invoice("friend@gmail.com", "Dinner tonight?"))

    def test_newsletter_not_invoice(self):
        self.assertFalse(is_invoice("news@techblog.com", "This week in tech"))

    def test_empty_not_invoice(self):
        self.assertFalse(is_invoice("", ""))

    def test_promo_not_invoice(self):
        self.assertFalse(is_invoice("deals@shop.com", "Save 50% today"))


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


if __name__ == "__main__":
    unittest.main()
