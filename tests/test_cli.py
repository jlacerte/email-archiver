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
