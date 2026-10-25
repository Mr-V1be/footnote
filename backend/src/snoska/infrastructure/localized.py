"""Localized texts as the data files of the product write them."""

from __future__ import annotations

from collections.abc import Mapping

from snoska.domain.shared.locale import Locale, LocalizedText


class IncompleteTranslationError(ValueError):
    """A text of a data file lacks the wording of an interface language."""


def read_localized(value: object, where: str) -> LocalizedText:
    """A text written in every interface language::

        title:
          ru: Поля страницы уже допустимых
          en: Page margins narrower than allowed

    A data file is the source of its texts: one without a wording in some
    language is refused when it is loaded, not shown half-translated.
    """
    if not isinstance(value, Mapping):
        raise IncompleteTranslationError(
            f"{where}: a text is written in every language ({', '.join(Locale)})"
        )
    wordings: dict[Locale, str] = {}
    for locale in Locale:
        wording = value.get(locale.value)
        if not isinstance(wording, str) or not wording.strip():
            raise IncompleteTranslationError(f"{where}: no {locale.value!r} wording")
        wordings[locale] = wording.strip()
    unknown = set(value) - {locale.value for locale in Locale}
    if unknown:
        raise IncompleteTranslationError(f"{where}: unknown languages {sorted(unknown)}")
    return LocalizedText(wordings)
