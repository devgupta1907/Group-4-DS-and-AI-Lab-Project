"""Field-level encryption for retained profile data.

The security architecture retains name, location, employer, institution, dates
and profile links because match quality depends on them — but requires them
encrypted at rest and decryptable only for the authenticated owner. The profile
JSON is therefore sealed as a single Fernet ciphertext; only non-sensitive
provenance (filename, route, page count, validity) stays queryable in clear.
"""

from __future__ import annotations

import json

from cryptography.fernet import Fernet, InvalidToken

from src.core.config import get_settings


class ProfileCipherUnavailable(RuntimeError):
    """Raised when the server has no encryption key configured."""


class ProfileCipher:
    """Seals and opens the candidate-profile payload."""

    def __init__(self, key: str) -> None:
        if not key:
            raise ProfileCipherUnavailable(
                "PROFILE_ENCRYPTION_KEY is not set. Generate one with: "
                'python -c "from cryptography.fernet import Fernet; '
                "print(Fernet.generate_key().decode())\""
            )
        self._fernet = Fernet(key.encode() if isinstance(key, str) else key)

    def seal(self, payload: dict) -> bytes:
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        return self._fernet.encrypt(raw)

    def open(self, token: bytes) -> dict:
        try:
            return json.loads(self._fernet.decrypt(token))
        except InvalidToken as exc:
            raise ProfileCipherUnavailable(
                "Stored profile could not be decrypted with the configured key."
            ) from exc


def build_cipher() -> ProfileCipher:
    return ProfileCipher(get_settings().profile_encryption_key)
