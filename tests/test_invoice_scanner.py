"""Tests for invoice scanner — classification, provider resolution, report building."""

import unittest
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

from email_archiver.invoice_scanner import (
    is_invoice, resolve_provider, extract_pdf_info, build_report,
    _provider_from_folder,
)


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

    def test_google_calendar_not_invoice(self):
        self.assertFalse(is_invoice(
            "calendar-notification@google.com",
            "Notification: AI Exploration Hour",
        ))

    def test_google_find_my_device_not_invoice(self):
        self.assertFalse(is_invoice(
            "noreply-findhub@google.com",
            "Localisation consultée pour Galaxy A16 5G",
        ))

    def test_google_accounts_not_invoice(self):
        self.assertFalse(is_invoice(
            "accounts.google.com",
            "Security alert for your Google Account",
        ))

    def test_google_payments_is_invoice(self):
        """Specific Google billing address should still match."""
        self.assertTrue(is_invoice(
            "payments-noreply@google.com",
            "Google Workspace subscription",
        ))


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
        """Helper: create a MIME email with a PDF attachment."""
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
        """Helper: create a plain text email with no attachments."""
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

        # Provider summary
        self.assertIn("Anthropic", report["providers"])
        self.assertEqual(report["providers"]["Anthropic"]["count"], 2)
        self.assertTrue(report["providers"]["Anthropic"]["has_pdf_attachments"])
        self.assertIn("2026-03", report["providers"]["Anthropic"]["months"])
        self.assertIn("2026-04", report["providers"]["Anthropic"]["months"])

        self.assertIn("Google", report["providers"])
        self.assertEqual(report["providers"]["Google"]["count"], 1)
        self.assertFalse(report["providers"]["Google"]["has_pdf_attachments"])
        self.assertTrue(report["providers"]["Google"]["link_only"])

        # Invoice list
        self.assertEqual(len(report["invoices"]), 3)

    def test_report_empty_invoices(self):
        report = build_report("gmail", [], total_scanned=500)
        self.assertEqual(report["invoices_found"], 0)
        self.assertEqual(report["providers"], {})
        self.assertEqual(report["invoices"], [])


if __name__ == "__main__":
    unittest.main()
