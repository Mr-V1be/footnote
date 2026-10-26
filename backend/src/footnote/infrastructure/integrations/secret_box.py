from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet


class FernetSecretBox:
    """Seals secrets with a key derived from the platform's configured secret
    (authenticated encryption; a changed or foreign value fails to open)."""

    def __init__(self, platform_secret: str) -> None:
        if not platform_secret:
            raise ValueError("SNOSKA_SECRETS_KEY is not set")
        key = base64.urlsafe_b64encode(hashlib.sha256(platform_secret.encode()).digest())
        self._fernet = Fernet(key)

    def seal(self, secret: str) -> str:
        return self._fernet.encrypt(secret.encode()).decode()

    def open(self, sealed: str) -> str:
        return self._fernet.decrypt(sealed.encode()).decode()
