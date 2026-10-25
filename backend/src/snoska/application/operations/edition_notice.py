"""The operators' mail about the weekly check of the corpus, in their language."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from snoska.domain.operations.schedule import EditionCheck, WatchOutcome
from snoska.domain.shared.locale import Locale
from snoska.ports.corpus.source import ActCatalog
from snoska.ports.operations.notifications import Email


@dataclass(frozen=True, slots=True)
class NoticeWording:
    """The mail's sentences; a line about an act takes the act's name as
    ``act`` and the ``revision`` or the ``error``, the status line its ``url``."""

    subject_new: str
    subject_failed: str
    opening: str
    new_edition: str
    failed: str
    closing_new: str
    closing_failed: str
    status: str


NOTICE_WORDINGS: Mapping[Locale, NoticeWording] = {
    Locale.RU: NoticeWording(
        subject_new="Сноска: новая редакция закона в корпусе",
        subject_failed="Сноска: не удалось проверить редакцию закона",
        opening="Еженедельная проверка корпуса норм.",
        new_edition="• {act}: на портале новая редакция ({revision}). Она загружена "
        "в корпус и стала действующей; индексация для поиска идёт в фоне.",
        failed="• {act}: не удалось проверить источник — {error}.",
        closing_new="Проверки документов, сделанные по прежней редакции, стоит повторить: "
        "snoska checks recheck.",
        closing_failed="Проверка повторится по расписанию; запустить её вручную: "
        "snoska corpus watch.",
        status="Состояние системы: {url}",
    ),
    Locale.EN: NoticeWording(
        subject_new="Snoska: a new edition of a law in the corpus",
        subject_failed="Snoska: the edition of a law could not be checked",
        opening="The weekly check of the corpus of norms.",
        new_edition="• {act}: the portal has a new edition ({revision}). It is loaded "
        "into the corpus and is now in force; it is being indexed for search in the background.",
        failed="• {act}: the source could not be checked: {error}.",
        closing_new="Documents checked against the previous edition are worth checking again: "
        "snoska checks recheck.",
        closing_failed="The check will run again on schedule; to run it now: snoska corpus watch.",
        status="System status: {url}",
    ),
}


def edition_notice(
    recipients: tuple[str, ...],
    checks: Sequence[EditionCheck],
    acts: ActCatalog,
    locale: Locale,
    web_url: str,
) -> Email:
    """What changed or failed, for operators who read ``locale``."""
    wording = NOTICE_WORDINGS[locale]
    lines: list[str] = []
    for check in checks:
        act = acts.get(check.act_code).act.short_title.resolve(locale)
        if check.outcome is WatchOutcome.NEW_EDITION:
            lines.append(wording.new_edition.format(act=act, revision=check.revision))
        else:
            lines.append(wording.failed.format(act=act, error=check.error))
    new = any(check.outcome is WatchOutcome.NEW_EDITION for check in checks)
    text = "\n\n".join(
        (
            wording.opening,
            "\n".join(lines),
            wording.closing_new if new else wording.closing_failed,
            wording.status.format(url=f"{web_url}/platform/system"),
        )
    )
    subject = wording.subject_new if new else wording.subject_failed
    return Email(to=recipients, subject=subject, text=text)
