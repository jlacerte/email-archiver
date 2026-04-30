"""Tests for IMAP client — mock-based, no real connections."""

import unittest
from unittest.mock import MagicMock, patch

from email_archiver.imap_client import IMAPClient, _decode_header_value


class TestDecodeHeaderValue(unittest.TestCase):

    def test_plain_ascii(self):
        self.assertEqual(_decode_header_value("Hello World"), "Hello World")

    def test_empty(self):
        self.assertEqual(_decode_header_value(""), "")

    def test_none(self):
        self.assertEqual(_decode_header_value(None), "")

    def test_utf8_encoded(self):
        # =?utf-8?Q?Caf=C3=A9?=
        result = _decode_header_value("=?utf-8?Q?Caf=C3=A9?=")
        self.assertEqual(result, "Café")

    def test_iso_encoded(self):
        result = _decode_header_value("=?iso-8859-1?Q?R=E9sum=E9?=")
        self.assertEqual(result, "Résumé")


class TestIMAPClientConnect(unittest.TestCase):

    @patch("email_archiver.imap_client.imaplib.IMAP4_SSL")
    def test_connect_success(self, mock_ssl):
        mock_conn = MagicMock()
        mock_ssl.return_value = mock_conn

        client = IMAPClient("imap.test.com", 993, "user", "pass")
        client.connect()

        mock_ssl.assert_called_once_with("imap.test.com", 993)
        mock_conn.login.assert_called_once_with("user", "pass")

    @patch("email_archiver.imap_client.imaplib.IMAP4_SSL")
    def test_select_folder(self, mock_ssl):
        mock_conn = MagicMock()
        mock_conn.select.return_value = ("OK", [b"42"])
        mock_ssl.return_value = mock_conn

        client = IMAPClient("imap.test.com", 993, "user", "pass")
        client.connect()
        count = client.select_folder("INBOX")

        self.assertEqual(count, 42)
        mock_conn.select.assert_called_once_with("INBOX")

    @patch("email_archiver.imap_client.imaplib.IMAP4_SSL")
    def test_search_all_uids(self, mock_ssl):
        mock_conn = MagicMock()
        mock_conn.uid.return_value = ("OK", [b"100 200 300"])
        mock_ssl.return_value = mock_conn

        client = IMAPClient("imap.test.com", 993, "user", "pass")
        client.connect()
        uids = client.search_all_uids()

        self.assertEqual(uids, [b"100", b"200", b"300"])

    @patch("email_archiver.imap_client.imaplib.IMAP4_SSL")
    def test_archive_uid_success(self, mock_ssl):
        mock_conn = MagicMock()
        mock_conn.uid.return_value = ("OK", [b"[COPYUID ...]"])
        mock_ssl.return_value = mock_conn

        client = IMAPClient("imap.test.com", 993, "user", "pass")
        client.connect()
        result = client.archive_uid(b"123", "Archive")

        self.assertTrue(result)

    @patch("email_archiver.imap_client.imaplib.IMAP4_SSL")
    def test_archive_uid_failure(self, mock_ssl):
        mock_conn = MagicMock()
        mock_conn.uid.return_value = ("NO", [b"error"])
        mock_ssl.return_value = mock_conn

        client = IMAPClient("imap.test.com", 993, "user", "pass")
        client.connect()
        result = client.archive_uid(b"123", "Archive")

        self.assertFalse(result)

    @patch("email_archiver.imap_client.imaplib.IMAP4_SSL")
    def test_disconnect_graceful(self, mock_ssl):
        mock_conn = MagicMock()
        mock_ssl.return_value = mock_conn

        client = IMAPClient("imap.test.com", 993, "user", "pass")
        client.connect()
        client.disconnect()

        mock_conn.logout.assert_called_once()
        self.assertIsNone(client._conn)


class TestFetchMessage(unittest.TestCase):

    @patch("email_archiver.imap_client.imaplib.IMAP4_SSL")
    def test_fetch_message_success(self, mock_ssl):
        """fetch_message returns a parsed email.message.Message on success."""
        raw_email = (
            b"From: billing@anthropic.com\r\n"
            b"Subject: Your invoice\r\n"
            b"Date: Thu, 01 Apr 2026 10:00:00 +0000\r\n"
            b"Content-Type: text/plain\r\n"
            b"\r\n"
            b"Here is your invoice.\r\n"
        )
        mock_conn = MagicMock()
        mock_conn.uid.return_value = ("OK", [
            (b"1 (UID 4532 BODY[] {123}", raw_email),
            b")",
        ])
        mock_ssl.return_value = mock_conn

        client = IMAPClient("imap.test.com", 993, "user", "pass")
        client.connect()
        msg = client.fetch_message(b"4532")

        self.assertIsNotNone(msg)
        self.assertIn("anthropic", msg["From"])
        self.assertEqual(msg["Subject"], "Your invoice")

    @patch("email_archiver.imap_client.imaplib.IMAP4_SSL")
    def test_fetch_message_failure_returns_none(self, mock_ssl):
        """fetch_message returns None when FETCH fails."""
        mock_conn = MagicMock()
        mock_conn.uid.return_value = ("NO", [b"FETCH failed"])
        mock_ssl.return_value = mock_conn

        client = IMAPClient("imap.test.com", 993, "user", "pass")
        client.connect()
        msg = client.fetch_message(b"9999")

        self.assertIsNone(msg)

    @patch("email_archiver.imap_client.imaplib.IMAP4_SSL")
    def test_fetch_message_exception_returns_none(self, mock_ssl):
        """fetch_message returns None when FETCH raises an exception."""
        mock_conn = MagicMock()
        mock_conn.uid.side_effect = Exception("Connection lost")
        mock_ssl.return_value = mock_conn

        client = IMAPClient("imap.test.com", 993, "user", "pass")
        client.connect()
        msg = client.fetch_message(b"9999")

        self.assertIsNone(msg)


if __name__ == "__main__":
    unittest.main()
