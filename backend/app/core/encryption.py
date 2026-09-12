"""
Encryption service — Fernet symmetric encryption for API keys and secrets.

Supports:
- Primary key from ENCRYPTION_KEY or ENCRYPTION_KEY_FILE (file preferred, for Docker secrets)
- Fallback historical keys (ENCRYPTION_FALLBACK_KEYS, comma-separated) used only when decrypting
  during key rotation windows.
"""

from __future__ import annotations

import logging
from pathlib import Path

from cryptography.fernet import Fernet, MultiFernet

from app.config import settings

logger = logging.getLogger(__name__)


def _load_primary_key(key: str | None, key_file: str | None) -> str:
    if key_file:
        path = Path(key_file)
        if path.is_file():
            raw = path.read_text(encoding="utf-8").strip()
            if raw:
                return raw
        logger.warning("ENCRYPTION_KEY_FILE set but unreadable/empty: %s", key_file)
    if key:
        return key
    raise ValueError(
        "ENCRYPTION_KEY is not set. Generate one with: "
        'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
    )


def _parse_fallback_keys(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


class EncryptionService:
    """Encrypts and decrypts sensitive values using Fernet (with optional key rotation)."""

    def __init__(
        self,
        key: str | None = None,
        fallback_keys: list[str] | None = None,
        key_file: str | None = None,
    ):
        primary = _load_primary_key(key, key_file)
        keys = [primary, *(fallback_keys or [])]
        # MultiFernet encrypts with the first key and decrypts with any
        self._fernets = [Fernet(k.encode() if isinstance(k, str) else k) for k in keys]
        self._multi = MultiFernet(self._fernets)

    def encrypt(self, value: str | None) -> str | None:
        """Encrypt a plaintext string. Returns None if value is None/empty."""
        if not value:
            return value
        return self._multi.encrypt(value.encode()).decode()

    def decrypt(self, encrypted: str | None) -> str | None:
        """Decrypt an encrypted string (tries primary then fallback keys)."""
        if not encrypted:
            return encrypted
        return self._multi.decrypt(encrypted.encode()).decode()

    def rotate(self, encrypted: str | None) -> str | None:
        """Re-encrypt an existing ciphertext under the current primary key."""
        if not encrypted:
            return encrypted
        return self._multi.rotate(encrypted.encode()).decode()


# Module-level singleton (lazy init so missing key doesn't crash import)
_encryption_service: EncryptionService | None = None


def get_encryption_service() -> EncryptionService:
    """Get or create the singleton EncryptionService."""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService(
            settings.encryption_key,
            fallback_keys=_parse_fallback_keys(settings.encryption_fallback_keys),
            key_file=settings.encryption_key_file or None,
        )
    return _encryption_service


def reset_encryption_service_for_tests() -> None:
    """Clear singleton so tests can re-init with different keys."""
    global _encryption_service
    _encryption_service = None
