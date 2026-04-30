"""Tests for CLI argument parsing."""

import unittest
from unittest.mock import patch, MagicMock

from email_archiver.cli import main


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


if __name__ == "__main__":
    unittest.main()
