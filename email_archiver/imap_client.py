"""
Persistent IMAP client using UIDs for all operations.

Key design decisions:
  - ONE connection per session (avoids Yahoo LOGIN rate-limit)
  - All operations use UIDs (stable across EXPUNGE, unlike sequence numbers)
  - COPY is verified before any STORE \\Deleted
  - Circuit breaker: 3 consecutive FETCH errors → stop
  - BODY.PEEK for header reads (does not mark as \\Seen)
"""

import email
import email.header
import imaplib
import logging
import re
from typing import List, Optional, Tuple

logger = logging.getLogger("email_archiver")


def _decode_header_value(raw: str) -> str:
    """Decode MIME-encoded header value to string."""
    if not raw:
        return ""
    decoded_parts = email.header.decode_header(raw)
    result = []
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(part)
    return " ".join(result)


class IMAPClient:
    """Persistent IMAP connection with UID-based operations."""

    def __init__(self, host: str, port: int, login: str, password: str):
        self.host = host
        self.port = port
        self.login_user = login
        self.password = password
        self._conn: Optional[imaplib.IMAP4_SSL] = None

    def connect(self) -> None:
        """Connect and login. Single LOGIN for the entire session."""
        self._conn = imaplib.IMAP4_SSL(self.host, self.port)
        logger.info("Connected to %s:%d", self.host, self.port)

        self._conn.login(self.login_user, self.password)
        logger.info("LOGIN OK.")

    def select_folder(self, folder: str) -> int:
        """Select a mailbox folder. Returns message count."""
        assert self._conn is not None, "Not connected"
        typ, data = self._conn.select(folder)
        if typ != "OK":
            raise imaplib.IMAP4.error(f"SELECT {folder} failed: {data}")
        count = int(data[0])
        logger.info("Selected '%s': %d messages", folder, count)
        return count

    def search_all_uids(self) -> List[bytes]:
        """UID SEARCH ALL — returns list of UIDs as bytes."""
        assert self._conn is not None, "Not connected"
        typ, data = self._conn.uid("SEARCH", None, "ALL")
        if typ != "OK":
            raise imaplib.IMAP4.error(f"UID SEARCH failed: {data}")
        uids = data[0].split() if data[0] else []
        logger.info("Found %d messages (UIDs).", len(uids))
        return uids

    def fetch_headers(self, uids: List[bytes]) -> List[Tuple[bytes, str, str]]:
        """Fetch From + Subject headers for a batch of UIDs.

        Returns list of (uid, from_addr, subject) tuples.
        Uses BODY.PEEK to avoid marking emails as \\Seen.
        """
        assert self._conn is not None, "Not connected"
        if not uids:
            return []

        uid_range = b",".join(uids)
        typ, fetch_data = self._conn.uid(
            "FETCH", uid_range, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])"
        )
        if typ != "OK":
            raise imaplib.IMAP4.error(f"UID FETCH failed: {fetch_data}")

        results = []
        for item in fetch_data:
            if not isinstance(item, tuple):
                continue

            # Extract UID from response line
            resp_line = (
                item[0].decode("utf-8", errors="replace")
                if isinstance(item[0], bytes)
                else str(item[0])
            )
            uid_match = re.search(r"UID\s+(\d+)", resp_line)
            if not uid_match:
                continue
            msg_uid = uid_match.group(1).encode()

            # Parse headers
            from_addr = ""
            subject = ""
            if len(item) >= 2 and isinstance(item[1], bytes):
                header_text = item[1].decode("utf-8", errors="replace")
                for line in header_text.split("\r\n"):
                    lower = line.lower()
                    if lower.startswith("from:"):
                        from_addr = _decode_header_value(line[5:].strip())
                    elif lower.startswith("subject:"):
                        subject = _decode_header_value(line[8:].strip())

            results.append((msg_uid, from_addr.lower(), subject))

        return results

    def fetch_message(self, uid: bytes) -> Optional["email.message.Message"]:
        """Fetch the complete message (headers + body + attachments).

        Uses BODY.PEEK[] to avoid marking the message as \\Seen.
        Returns a parsed email.message.Message, or None on failure.
        """
        assert self._conn is not None, "Not connected"
        try:
            typ, fetch_data = self._conn.uid("FETCH", uid, "(BODY.PEEK[])")
            if typ != "OK":
                logger.error("UID FETCH failed for %s: %s", uid.decode(), fetch_data)
                return None

            for item in fetch_data:
                if isinstance(item, tuple) and len(item) >= 2:
                    raw_bytes = item[1]
                    if isinstance(raw_bytes, bytes):
                        return email.message_from_bytes(raw_bytes)

            logger.error("No message body found in FETCH response for UID %s", uid.decode())
            return None
        except Exception as e:
            logger.error("FETCH exception for UID %s: %s", uid.decode(), e)
            return None

    def archive_uid(self, uid: bytes, archive_folder: str) -> bool:
        """COPY uid to archive folder, verify OK.

        Returns True if COPY succeeded. Does NOT delete — caller handles that.
        This separation ensures we never delete without a confirmed copy.
        """
        assert self._conn is not None, "Not connected"
        # Quote folder names for IMAP (spaces cause parse errors)
        quoted = f'"{archive_folder}"'
        typ, _ = self._conn.uid("COPY", uid, quoted)
        return typ == "OK"

    def mark_deleted(self, uids: List[bytes]) -> None:
        """Mark UIDs as \\Deleted. Only call after confirmed COPY."""
        assert self._conn is not None, "Not connected"
        if not uids:
            return
        uid_set = b",".join(uids)
        self._conn.uid("STORE", uid_set, "+FLAGS", "(\\Deleted)")

    def expunge(self) -> None:
        """EXPUNGE — permanently remove messages marked \\Deleted."""
        assert self._conn is not None, "Not connected"
        self._conn.expunge()

    def disconnect(self) -> None:
        """LOGOUT gracefully."""
        if self._conn is not None:
            try:
                self._conn.logout()
                logger.info("LOGOUT OK.")
            except Exception as e:
                logger.warning("LOGOUT error (non-fatal): %s", e)
            finally:
                self._conn = None
