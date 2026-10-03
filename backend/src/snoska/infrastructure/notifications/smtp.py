from __future__ import annotations

from dataclasses import dataclass
from email.message import EmailMessage

import aiosmtplib

from snoska.ports.operations.notifications import Email


@dataclass(frozen=True, slots=True)
class SmtpConfig:
    host: str
    port: int
    sender: str
    username: str | None = None
    password: str | None = None
    start_tls: bool = False


class SmtpMailer:
    """Plain-text email over SMTP (Mailpit on the stand)."""

    def __init__(self, config: SmtpConfig) -> None:
        self._config = config

    async def send(self, email: Email) -> None:
        message = EmailMessage()
        message["From"] = self._config.sender
        message["To"] = ", ".join(email.to)
        message["Subject"] = email.subject
        message.set_content(email.text)
        await aiosmtplib.send(
            message,
            hostname=self._config.host,
            port=self._config.port,
            username=self._config.username,
            password=self._config.password,
            start_tls=self._config.start_tls,
        )
