"""Renders a benchmark result as docs/quality.md (Russian, for the repository)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from snoska.domain.checks.catalog import CheckCatalog, CheckMethod
from snoska.domain.checks.quality import DocumentTiming, Metrics, QualityReport

_FAMILIES = {
    "formatting": "Оформление по ГОСТ Р 7.0.97-2016",
    "personal_data": "Персональные данные по 152-ФЗ",
}
_METHODS = {
    CheckMethod.DETERMINISTIC: "Правила (без модели)",
    CheckMethod.MODEL: "Языковая модель",
}
_KINDS = {
    "pd_policy": "Политика ПДн",
    "pd_consent": "Согласие на обработку ПДн",
    "pd_assignment": "Поручение обработки ПДн",
    "contract": "Договор",
    "regulation": "Положение",
    "order": "Приказ",
    "other": "Другое",
}
_NOT_MEASURED = "не измерено"
# Measured, but the share has no cases to count (nothing reported or expected).
_NO_CASES = "—"
_HEADER = (
    "| {label} | Наблюдений | Точность | Полнота | Найдено верно | Найдено ложно "
    "| Пропущено | Верно без замечаний | «Юристу» | Не выполнено |\n"
    "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"
)


def _share(value: float | None) -> str:
    return _NO_CASES if value is None else f"{value:.0%}".replace("%", "\u00a0%")


def _seconds(milliseconds: int | None) -> str:
    if milliseconds is None:
        return _NOT_MEASURED
    return f"{milliseconds / 1000:.2f}".replace(".", ",") + "\u00a0с"


def _row(label: str, metrics: Metrics) -> str:
    measured = metrics.observations - metrics.errors
    precision = _share(metrics.precision) if measured else _NOT_MEASURED
    recall = _share(metrics.recall) if measured else _NOT_MEASURED
    return (
        f"| {label} | {metrics.observations} | {precision} | {recall} "
        f"| {metrics.true_positives} | {metrics.false_positives} | {metrics.false_negatives} "
        f"| {metrics.true_negatives} | {metrics.reviews} | {metrics.errors} |"
    )


def _table(label: str, rows: Iterable[tuple[str, Metrics]]) -> list[str]:
    return [_HEADER.format(label=label), *(_row(name, metrics) for name, metrics in rows)]


def _timing_row(item: DocumentTiming) -> str:
    name = f"**{item.title}** (типовой)" if item.typical else item.title
    return (
        f"| {name} | {item.pages} | {_seconds(item.parse_ms)} "
        f"| {_seconds(item.deterministic_ms)} | {_seconds(item.model_ms)} "
        f"| {_seconds(item.total_ms)} |"
    )


def _misses(report: QualityReport, titles: Mapping[str, str]) -> list[str]:
    lines = []
    for item in report.observations:
        status = item.status.value
        if item.method is CheckMethod.MODEL and report.model is None:
            continue
        missed = item.expected_violation and status != "violation"
        extra = not item.expected_violation and status == "violation"
        if missed or extra:
            verdict = "пропущено" if missed else "лишнее замечание"
            title = titles.get(item.check_code, item.check_code)
            lines.append(f"- `{item.document}` — {title} (`{item.check_code}`): {verdict}.")
    return lines or ["Расхождений с разметкой нет."]


def _labelled(report: QualityReport, file_name: str) -> int:
    return sum(
        1 for item in report.observations if item.document == file_name and item.expected_violation
    )


def render(report: QualityReport, catalog: CheckCatalog) -> str:
    titles = {check.code: check.title for check in catalog.all()}
    model = report.model or "не подключена — юридические проверки не измерены"
    by_method = report.by_method()
    by_family = report.by_family()
    by_check = report.by_check()
    lines = [
        "# Качество проверок",
        "",
        "> Файл создаёт команда `make benchmark` (`snoska checks benchmark`). "
        "Не правьте его вручную: перезапустите замер.",
        "",
        f"Замер: {report.measured_at:%d.%m.%Y %H:%M} UTC · ревизия реестра проверок "
        f"`{report.catalog_revision}` · модель: {model}.",
        "",
        "## Как считаем",
        "",
        f"- Эталонный набор — {len(report.documents)} документов, которые мы написали сами "
        "(`backend/demo/reference`). В `labels.yaml` для каждого документа перечислены "
        "нарушения, которые находит эксперт.",
        "- Наблюдение — одна проверка на одном документе. Нарушение — положительный класс: "
        "**точность** — доля верных среди найденных нарушений, **полнота** — доля найденных "
        "среди размеченных.",
        "- Ответ «требует проверки юристом» не считается найденным нарушением: для полноты "
        "это пропуск. Число таких ответов показано отдельно.",
        "- Проверки, которые не выполнились (например, модель не подключена), в точность и "
        "полноту не входят и показаны в столбце «Не выполнено».",
        "- «—» — считать не из чего: проверка не нашла ни одного нарушения (точность) или "
        "в наборе нет размеченных для неё нарушений (полнота).",
        "",
        "## По способу проверки",
        "",
        *_table(
            "Способ",
            (
                (_METHODS[method], by_method[method])
                for method in CheckMethod
                if method in by_method
            ),
        ),
        "",
        "## По семействам",
        "",
        *_table(
            "Семейство",
            (
                (_FAMILIES.get(family.code, family.code), by_family[family.code])
                for family in catalog.families()
                if family.code in by_family
            ),
        ),
        "",
        "## По проверкам",
        "",
        *_table(
            "Проверка",
            (
                (f"{check.title} (`{check.code}`)", by_check[check.code])
                for check in catalog.all()
                if check.code in by_check
            ),
        ),
        "",
        "## Расхождения с разметкой",
        "",
        *_misses(report, titles),
        "",
        "## Время проверки",
        "",
        "Документы разбираются и проверяются так же, как в продукте; правила и модель "
        "запускаются по очереди, чтобы у каждой части было своё время. В продукте они "
        "идут параллельно.",
        "",
        "| Документ | Страниц | Разбор | Правила | Языковая модель | Всего |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
        *(_timing_row(item) for item in report.documents),
        "",
    ]
    if report.model is None:
        lines += [
            "Юридическая часть не измерена: внешний API модели не подключён. Замер повторяется "
            "той же командой после того, как в `.env` заданы провайдер и ключ.",
            "",
        ]
    lines += [
        "## Документы набора",
        "",
        "| Файл | Вид | Страниц | Размеченных нарушений |",
        "| --- | --- | ---: | ---: |",
        *(
            f"| `{item.file_name}` | {_KINDS.get(item.kind, item.kind)} | {item.pages} "
            f"| {_labelled(report, item.file_name)} |"
            for item in report.documents
        ),
        "",
    ]
    return "\n".join(lines)
