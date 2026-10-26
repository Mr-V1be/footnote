"""How instructions to the language model name the interface languages.

The instructions are written in Russian, the language of the documents and
of the law; what the model writes for a reader it writes in their language.
"""

from __future__ import annotations

from collections.abc import Mapping

from footnote.domain.shared.locale import Locale

# Adverbs as the instructions use them: «пиши по-английски».
LANGUAGE_NAMES: Mapping[Locale, str] = {Locale.RU: "по-русски", Locale.EN: "по-английски"}
