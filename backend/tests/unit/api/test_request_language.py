"""The language a request is answered in, from what the reader asked for."""

from __future__ import annotations

import pytest

from footnote.api.locale import preferred_locale
from footnote.domain.shared.locale import Locale


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("en", Locale.EN),
        ("ru-RU,ru;q=0.9,en;q=0.8", Locale.RU),
        ("de-DE,de;q=0.9,en-US;q=0.7,ru;q=0.6", Locale.EN),
        ("ru;q=0.4, en;q=0.8", Locale.EN),
        ("en;q=0, ru", Locale.RU),
        ("en,ru", Locale.EN),
        ("de, fr;q=0.8, *;q=0.5", None),
        ("", None),
        (None, None),
    ],
    ids=[
        "one language",
        "a Russian browser",
        "the first supported by weight",
        "weights over order",
        "a refused language",
        "order between equals",
        "nothing supported",
        "empty",
        "absent",
    ],
)
def test_the_most_preferred_supported_language_is_taken(
    header: str | None, expected: Locale | None
) -> None:
    assert preferred_locale(header) is expected
