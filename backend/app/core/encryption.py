"""
Encryption service — Fernet symmetric encryption for API keys and secrets.
"""

from cryptography.fernet import Fernet

from app.config import settings


class EncryptionService:
    """Encrypts and decrypts sensitive values using Fernet symmetric encryption."""

    def __init__(self, key: str | None = None):
        if not key:
            raise ValueError(
                "ENCRYPTION_KEY is not set. Generate one with: "
                'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
            )
        self._fernet = Fernet(key.encode() if isinstance(key, str) else key)

    def encrypt(self, value: str | None) -> str | None:
        """Encrypt a plaintext string. Returns None if value is None/empty."""
        if not value:
            return value
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, encrypted: str | None) -> str | None:
        """Decrypt an encrypted string. Returns None if value is None/empty."""
        if not encrypted:
            return encrypted
        return self._fernet.decrypt(encrypted.encode()).decode()


# Module-level singleton (lazy init so missing key doesn't crash import)
_encryption_service: EncryptionService | None = None


def get_encryption_service() -> EncryptionService:
    """Get or create the singleton EncryptionService."""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService(settings.encryption_key)
    return _encryption_service
