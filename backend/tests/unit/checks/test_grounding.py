"""A quote counts only if the document says it, word for word."""

from __future__ import annotations

import pytest

from footnote.domain.checks.grounding import locate_quote

TEXT = "Оператор обрабатывает персональные данные «клиентов» — в целях\nисполнения договоров."


def test_quote_is_found_regardless_of_case_spacing_and_quote_marks() -> None:
    span = locate_quote(TEXT, 'оператор  обрабатывает персональные данные "клиентов" - в целях')
    assert span is not None
    assert TEXT[span[0] : span[1]].startswith("Оператор")


def test_parts_joined_by_an_ellipsis_must_appear_in_order() -> None:
    span = locate_quote(TEXT, "Оператор обрабатывает … исполнения договоров.")
    assert span == (0, len(TEXT) - 1)
    assert locate_quote(TEXT, "исполнения договоров … Оператор обрабатывает") is None


def test_a_table_row_quoted_with_cell_separators_matches_the_tabbed_text() -> None:
    row = "Оформление заказов\tПокупатели\tФИО, телефон"
    assert locate_quote(row, "Оформление заказов | Покупатели") is not None


@pytest.mark.parametrize("quote", ["данные", "Оператор хранит данные клиентов"])
def test_too_short_or_invented_quotes_are_rejected(quote: str) -> None:
    assert locate_quote(TEXT, quote) is None
