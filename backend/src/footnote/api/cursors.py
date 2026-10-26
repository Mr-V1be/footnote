from __future__ import annotations

import base64
import json
from datetime import datetime
from uuid import UUID

from footnote.domain.shared.errors import ValidationError
from footnote.ports.document_repositories import DocumentCursor
from footnote.ports.pagination import TimeCursor


class InvalidCursorError(ValidationError):
    code = "invalid_cursor"


def encode_cursor(cursor: DocumentCursor) -> str:
    raw = json.dumps({"u": cursor.updated_at.isoformat(), "i": str(cursor.id)}).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(value: str) -> DocumentCursor:
    try:
        padded = value + "=" * (-len(value) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded))
        return DocumentCursor(updated_at=datetime.fromisoformat(data["u"]), id=UUID(data["i"]))
    except (ValueError, KeyError, TypeError) as exc:
        raise InvalidCursorError("cursor is malformed") from exc


def encode_time_cursor(cursor: TimeCursor) -> str:
    raw = json.dumps({"t": cursor.at.isoformat(), "i": str(cursor.id)}).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_time_cursor(value: str) -> TimeCursor:
    try:
        padded = value + "=" * (-len(value) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded))
        return TimeCursor(at=datetime.fromisoformat(data["t"]), id=UUID(data["i"]))
    except (ValueError, KeyError, TypeError) as exc:
        raise InvalidCursorError("cursor is malformed") from exc
