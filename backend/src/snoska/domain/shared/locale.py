"""The languages the product speaks to people in, and texts written in each."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum


class Locale(StrEnum):
    """An interface language. Adding one is adding a member here and its
    wording to every localized text of the catalogues; loading refuses a
    catalogue that misses it."""

    RU = "ru"
    EN = "en"


# The language of what the product checks — documents, the law, the
# standard — and the one its own texts are written in first. Every localized
# text has it, and it is what a reader gets when nothing tells their language.
SOURCE_LOCALE = Locale.RU


def parse_locale(value: str | None) -> Locale | None:
    """A supported locale named by a language tag ("en", "ru-RU"), if any."""
    if not value:
        return None
    primary = value.strip().split("-", 1)[0].split("_", 1)[0].lower()
    return next((locale for locale in Locale if locale.value == primary), None)


@dataclass(frozen=True, slots=True)
class LocalizedText:
    """One text in the interface languages.

    The source wording is always there. A text recorded before a language
    was supported may lack its wording; the source wording stands in for it.
    """

    values: Mapping[Locale, str]

    def __post_init__(self) -> None:
        if not self.values.get(SOURCE_LOCALE, "").strip():
            raise ValueError(f"a localized text needs its {SOURCE_LOCALE.value} wording")
        if any(not wording.strip() for wording in self.values.values()):
            raise ValueError("a localized text has no empty wordings")

    @classmethod
    def source(cls, wording: str) -> LocalizedText:
        return cls({SOURCE_LOCALE: wording})

    @classmethod
    def from_mapping(cls, raw: Mapping[str, str]) -> LocalizedText:
        """From stored or configured wordings by language code; codes of
        languages no longer supported are left out."""
        values = {locale: raw[locale.value] for locale in Locale if raw.get(locale.value)}
        return cls(values)

    def as_mapping(self) -> dict[str, str]:
        return {locale.value: wording for locale, wording in self.values.items()}

    @property
    def missing(self) -> tuple[Locale, ...]:
        """Languages this text has no wording in."""
        return tuple(locale for locale in Locale if locale not in self.values)

    def resolve(self, locale: Locale) -> str:
        return self.values.get(locale) or self.values[SOURCE_LOCALE]
