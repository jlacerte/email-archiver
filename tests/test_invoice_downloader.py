"""Tests for invoice downloader — PDF extraction, naming, CSV generation."""

import csv
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

from email_archiver.invoice_downloader import make_pdf_filename, extract_and_save_pdfs, write_csv


class TestMakePdfFilename(unittest.TestCase):
    """Test PDF filename generation."""

    def test_normal_filename(self):
        result = make_pdf_filename("2026-04-01", "invoice-march.pdf", "Anthropic")
        self.assertEqual(result, "2026-04-01-invoice-march.pdf")

    def test_generic_filename_gets_provider_prefix(self):
        result = make_pdf_filename("2026-04-01", "invoice.pdf", "Anthropic")
        self.assertEqual(result, "2026-04-01-anthropic-invoice.pdf")

    def test_generic_document_pdf(self):
        result = make_pdf_filename("2026-04-01", "document.pdf", "Google")
        self.assertEqual(result, "2026-04-01-google-document.pdf")

    def test_no_date(self):
        result = make_pdf_filename("", "invoice-123.pdf", "Anthropic")
        self.assertEqual(result, "invoice-123.pdf")

    def test_filename_already_has_provider(self):
        """If filename already contains provider-like info, just prepend date."""
        result = make_pdf_filename("2026-04-01", "anthropic-invoice-march.pdf", "Anthropic")
        self.assertEqual(result, "2026-04-01-anthropic-invoice-march.pdf")


class TestExtractAndSavePdfs(unittest.TestCase):
    """Test PDF extraction and saving from email messages."""

    def _make_email_with_pdf(self, filename="invoice.pdf", content=b"%PDF-fake"):
        msg = MIMEMultipart()
        msg["From"] = "billing@anthropic.com"
        msg["Subject"] = "Your invoice"
        msg["Date"] = "Wed, 01 Apr 2026 10:00:00 +0000"
        msg.attach(MIMEText("Invoice attached."))

        pdf = MIMEBase("application", "pdf")
        pdf.set_payload(content)
        encoders.encode_base64(pdf)
        pdf.add_header("Content-Disposition", "attachment", filename=filename)
        msg.attach(pdf)
        return msg

    def test_extracts_pdf_to_directory(self):
        msg = self._make_email_with_pdf("invoice-march.pdf", b"%PDF-test-content")
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            saved = extract_and_save_pdfs(msg, "2026-04-01", "Anthropic", output_dir)

            self.assertEqual(len(saved), 1)
            saved_path = output_dir / saved[0]
            self.assertTrue(saved_path.exists())
            self.assertEqual(saved_path.read_bytes(), b"%PDF-test-content")

    def test_skips_existing_same_size(self):
        msg = self._make_email_with_pdf("invoice.pdf", b"%PDF-content")
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            # First extraction
            saved1 = extract_and_save_pdfs(msg, "2026-04-01", "Anthropic", output_dir)
            # Second extraction — should skip
            saved2 = extract_and_save_pdfs(msg, "2026-04-01", "Anthropic", output_dir)
            self.assertEqual(len(saved1), 1)
            self.assertEqual(len(saved2), 0)

    def test_no_attachments_returns_empty(self):
        msg = MIMEText("No attachments here.")
        msg["From"] = "billing@example.com"
        msg["Date"] = "Wed, 01 Apr 2026 10:00:00 +0000"
        with tempfile.TemporaryDirectory() as tmpdir:
            saved = extract_and_save_pdfs(msg, "2026-04-01", "Example", Path(tmpdir))
            self.assertEqual(len(saved), 0)


class TestWriteCsv(unittest.TestCase):
    """Test CSV summary generation."""

    def test_csv_output(self):
        rows = [
            {
                "date": "2026-04-01",
                "fournisseur": "Anthropic",
                "sujet": "Your March invoice",
                "fichier_pdf": "2026-04-01-invoice.pdf",
                "source_email": "billing@anthropic.com",
            },
            {
                "date": "2026-04-15",
                "fournisseur": "Telus",
                "sujet": "Votre facture",
                "fichier_pdf": "",
                "source_email": "factures@telus.com",
            },
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "recapitulatif.csv"
            write_csv(rows, csv_path)

            self.assertTrue(csv_path.exists())
            content = csv_path.read_text(encoding="utf-8-sig")
            reader = csv.DictReader(io.StringIO(content))
            result_rows = list(reader)

            self.assertEqual(len(result_rows), 2)
            self.assertEqual(result_rows[0]["fournisseur"], "Anthropic")
            self.assertEqual(result_rows[1]["fichier_pdf"], "")

    def test_csv_empty_rows(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "recapitulatif.csv"
            write_csv([], csv_path)

            self.assertTrue(csv_path.exists())
            content = csv_path.read_text(encoding="utf-8-sig")
            reader = csv.DictReader(io.StringIO(content))
            self.assertEqual(len(list(reader)), 0)


if __name__ == "__main__":
    unittest.main()
