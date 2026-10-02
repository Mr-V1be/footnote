from __future__ import annotations

import os
import time
from uuid import UUID


def new_id() -> UUID:
    """Return a time-ordered UUIDv7 (RFC 9562).

    Time ordering keeps B-tree inserts local and makes ids sortable by
    creation time, which keyset pagination relies on.
    """
    unix_ms = time.time_ns() // 1_000_000
    rand = int.from_bytes(os.urandom(10), "big")
    rand_a = rand >> 68 & 0xFFF
    rand_b = rand & 0x3FFF_FFFF_FFFF_FFFF
    value = (unix_ms & 0xFFFF_FFFF_FFFF) << 80
    value |= 0x7 << 76
    value |= rand_a << 64
    value |= 0b10 << 62
    value |= rand_b
    return UUID(int=value)
