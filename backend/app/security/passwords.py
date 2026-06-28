"""Password hashing using standard-library PBKDF2-HMAC."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os


class PasswordHasher:
    """Hashes and verifies passwords with PBKDF2-HMAC-SHA256."""

    def __init__(self, iterations: int = 260_000) -> None:
        """Create a password hasher with a configurable work factor."""
        self._iterations = iterations

    def hash(self, password: str) -> str:
        """Return an encoded password hash."""
        salt = os.urandom(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, self._iterations)
        return "pbkdf2_sha256${}${}${}".format(
            self._iterations,
            base64.urlsafe_b64encode(salt).decode("ascii"),
            base64.urlsafe_b64encode(digest).decode("ascii"),
        )

    def verify(self, password: str, encoded_hash: str) -> bool:
        """Return whether a password matches an encoded hash."""
        algorithm, iteration_text, salt_text, digest_text = encoded_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iteration_text)
        salt = base64.urlsafe_b64decode(salt_text.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_text.encode("ascii"))
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual, expected)

