from __future__ import annotations

import structlog

from snoska.application.corpus.sync import CorpusSync, SyncOutcome
from snoska.domain.operations.schedule import EditionCheck, WatchOutcome
from snoska.domain.shared.ids import new_id
from snoska.ports.clock import Clock
from snoska.ports.corpus_source import ActCatalog, CorpusSourceError
from snoska.ports.jobs import JobPayload
from snoska.ports.operations.notifications import Email, Mailer, PlatformAdmins
from snoska.ports.unit_of_work import UnitOfWorkFactory

log = structlog.get_logger(__name__)

OFFICIAL_SOURCE = "pravo_ips"


class WatchCorpusEditions:
    """Weekly job: is there a newer redaction of a tracked act on the
    official portal? A new one is loaded into the corpus (and indexed in the
    background); the platform's administrators get an email either way it
    matters — a new edition, or a source that could not be read."""

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        catalog: ActCatalog,
        sync: CorpusSync,
        admins: PlatformAdmins,
        mailer: Mailer,
        clock: Clock,
        *,
        web_url: str,
        source: str = OFFICIAL_SOURCE,
    ) -> None:
        self._uow_factory = uow_factory
        self._catalog = catalog
        self._sync = sync
        self._admins = admins
        self._mailer = mailer
        self._clock = clock
        self._web_url = web_url.rstrip("/")
        self._source = source

    async def __call__(self, payload: JobPayload) -> None:
        del payload
        await self.run()

    async def run(self) -> list[EditionCheck]:
        checks = [await self._check(tracked.act.code) for tracked in self._catalog.all()]
        async with self._uow_factory.for_platform() as uow:
            for check in checks:
                await uow.edition_checks.add(check)
            await uow.commit()
        notable = [check for check in checks if check.outcome is not WatchOutcome.UNCHANGED]
        if notable:
            recipients = tuple(await self._admins.emails())
            if recipients:
                await self._mailer.send(self._email(recipients, notable))
        return checks

    async def _check(self, act_code: str) -> EditionCheck:
        now = self._clock.now()
        try:
            result = await self._sync.sync(act_code, self._source)
        except CorpusSourceError as exc:
            log.warning("corpus.watch_failed", act=act_code, error=str(exc))
            return EditionCheck(
                id=new_id(),
                act_code=act_code,
                checked_at=now,
                outcome=WatchOutcome.FAILED,
                revision=None,
                edition_id=None,
                error=str(exc)[:500],
            )
        outcome = (
            WatchOutcome.NEW_EDITION
            if result.outcome is SyncOutcome.INGESTED
            else WatchOutcome.UNCHANGED
        )
        log.info("corpus.watched", act=act_code, outcome=outcome, revision=result.source_revision)
        return EditionCheck(
            id=new_id(),
            act_code=act_code,
            checked_at=now,
            outcome=outcome,
            revision=result.source_revision,
            edition_id=result.edition_id,
        )

    def _email(self, recipients: tuple[str, ...], checks: list[EditionCheck]) -> Email:
        lines: list[str] = []
        for check in checks:
            title = self._catalog.get(check.act_code).act.short_title
            if check.outcome is WatchOutcome.NEW_EDITION:
                lines.append(
                    f"• {title}: на портале новая редакция ({check.revision}). Она загружена "
                    "в корпус и стала действующей; индексация для поиска идёт в фоне."
                )
            else:
                lines.append(f"• {title}: не удалось проверить источник — {check.error}.")
        new = any(check.outcome is WatchOutcome.NEW_EDITION for check in checks)
        subject = (
            "Сноска: новая редакция закона в корпусе"
            if new
            else "Сноска: не удалось проверить редакцию закона"
        )
        footer = (
            "Проверки документов, сделанные по прежней редакции, стоит повторить: "
            "snoska checks recheck."
            if new
            else "Проверка повторится по расписанию; запустить её вручную: snoska corpus watch."
        )
        text = "\n\n".join(
            (
                "Еженедельная проверка корпуса норм.",
                "\n".join(lines),
                footer,
                f"Состояние системы: {self._web_url}/platform/system",
            )
        )
        return Email(to=recipients, subject=subject, text=text)
