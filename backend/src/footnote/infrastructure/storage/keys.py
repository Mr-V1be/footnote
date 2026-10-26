from __future__ import annotations

import re

_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,511}$")


def validate_key(key: str) -> str:
    """Blob keys are relative paths of safe characters, never escaping upwards."""
    if not _KEY.fullmatch(key) or ".." in key.split("/"):
        raise ValueError(f"invalid blob key {key!r}")
    return key
