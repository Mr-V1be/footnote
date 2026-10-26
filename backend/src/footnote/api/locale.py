"""The language a request is answered in.

The reader states it in ``Accept-Language``; the web app always does, with
the language its visitor chose. Without a supported language there the API
answers in the source language, as it always has, so integrations written
against it read what they read before.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, Response

from footnote.domain.shared.locale import SOURCE_LOCALE, Locale, parse_locale

LANGUAGE_HEADER = "Accept-Language"


def _weight(parameters: str) -> float:
    for parameter in parameters.split(";"):
        name, _, value = parameter.strip().partition("=")
        if name.strip().lower() == "q":
            try:
                return float(value)
            except ValueError:
                return 0.0
    return 1.0


def preferred_locale(header: str | None) -> Locale | None:
    """The supported language the reader prefers most (RFC 9110 weights;
    among equal weights the first listed), if they named any."""
    if not header:
        return None
    ranked: list[tuple[float, int, Locale]] = []
    for position, item in enumerate(header.split(",")):
        tag, _, parameters = item.partition(";")
        weight = _weight(parameters)
        locale = parse_locale(tag)
        if locale is not None and weight > 0:
            ranked.append((-weight, position, locale))
    return min(ranked)[2] if ranked else None


def get_stated_locale(
    accept_language: Annotated[
        str | None,
        Header(
            alias=LANGUAGE_HEADER,
            description="Languages the reader reads, e.g. `en` or `ru`; texts the "
            "product writes (titles, requirements, explanations, citations) come in "
            "the first supported one, in Russian when none is.",
        ),
    ] = None,
) -> Locale | None:
    return preferred_locale(accept_language)


StatedLocaleDep = Annotated[Locale | None, Depends(get_stated_locale)]


def get_locale(response: Response, stated: StatedLocaleDep) -> Locale:
    locale = stated or SOURCE_LOCALE
    response.headers["Content-Language"] = locale.value
    response.headers["Vary"] = LANGUAGE_HEADER
    return locale


LocaleDep = Annotated[Locale, Depends(get_locale)]
