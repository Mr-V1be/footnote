/**
 * Russian typesetting rules: spans of text that must stay on one line.
 *
 * Each rule matches a construction a reader perceives as one unit — a document
 * number, a reference to a norm, a date, initials with a surname. A new rule is
 * a new entry; the typesetter applies every entry the same way.
 */
export interface TypographicRule {
  /** Stable name, used in tests and diagnostics. */
  readonly id: string;
  /** Global, Unicode-aware pattern; every match is kept on one line. */
  readonly pattern: RegExp;
}

/** No letter or digit right before / after the match: a whole-word boundary that works for Cyrillic. */
const START = String.raw`(?<![\p{L}\p{N}])`;
const END = String.raw`(?![\p{L}\p{N}])`;
const CODE = String.raw`[\p{L}\p{N}]+(?:[-\u2010\u2011\u2013/.][\p{L}\p{N}]+)*`;
const NUMBER = String.raw`\p{N}+(?:[.,]\p{N}+)*`;
const MONTHS = "января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря";
/** Structural units of a legal act or a document: «п. 2», «ч. 1», «ст. 18.1», «разд. 3». */
const UNIT = String.raw`(?:пп?|подп|ч|ст|гл|разд|абз|прил|рис|табл)\.\s*${NUMBER}`;
const INITIALS = String.raw`\p{Lu}\.\s?(?:\p{Lu}\.)?`;
const SURNAME = String.raw`\p{Lu}\p{Ll}+(?:-\p{Lu}\p{Ll}+)?`;

function rule(id: string, source: string, flags = ""): TypographicRule {
  return { id, pattern: new RegExp(source, `gu${flags}`) };
}

export const TYPOGRAPHIC_RULES: readonly TypographicRule[] = [
  // «№ 7-ОД», «№ 152-ФЗ», «№ 15/2026», «§ 4».
  rule("number-sign", String.raw`[№§]\s*${CODE}`),
  // «п. 2 ч. 1 ст. 18.1 152-ФЗ»: a chain of units reads as one reference.
  rule("norm-reference", String.raw`${START}${UNIT}(?:\s+${UNIT})*(?:\s+\p{N}+-ФЗ)?${END}`, "i"),
  // «ГОСТ Р 7.0.97-2016».
  rule("standard", String.raw`${START}ГОСТ(?:\s+Р)?(?:\s+ИСО(?:\/МЭК)?)?\s+${NUMBER}(?:-\p{N}+)?`),
  // Codes with a hyphen or a slash and a digit: «7-ОД», «152-ФЗ», «15/2026».
  rule(
    "code",
    String.raw`${START}\p{N}+(?:[-\u2010\u2011\u2013/]\p{L}+|[-\u2010\u2011\u2013/]\p{N}+)+${END}`,
  ),
  // «14.01.2026», «14.01.2026 г.».
  rule("date", String.raw`${START}\p{N}{1,2}\.\p{N}{1,2}\.\p{N}{2,4}(?:\s?гг?\.)?`),
  // «3 февраля 2026 г.», ««03» февраля 2026 года».
  rule(
    "date-in-words",
    String.raw`«?${START}\p{N}{1,2}»?\s+(?:${MONTHS})(?:\s+\p{N}{4}(?:\s?(?:гг?\.|года))?)?${END}`,
    "i",
  ),
  // «2026 г.», «2025–2026 гг.».
  rule("year", String.raw`${START}\p{N}{4}(?:[–-]\p{N}{4})?\s?гг?\.`),
  // «А.С. Ковалёва», «Ковалёва А. С.».
  rule("initials-first", String.raw`${START}${INITIALS}\s?${SURNAME}${END}`),
  rule("surname-first", String.raw`${START}${SURNAME}\s${INITIALS}`),
  // «г. Москва», «ул. Ленина», «д. 5», «кв. 12».
  rule(
    "address",
    String.raw`${START}(?:г|пос|с|д|ул|пр|пер|пл|наб|корп|стр|кв|оф|обл)\.\s?[\p{Lu}\p{N}][\p{L}\p{N}-]*`,
  ),
  // «25 МБ», «30 %», «100 руб.», «1 экз.».
  rule(
    "number-unit",
    String.raw`${START}${NUMBER}\s(?:%|‰|₽|руб\.|коп\.|[КМГТ]Б|мм|см|км|кг|экз\.|стр\.|л\.)`,
  ),
  // «т. е.», «т. д.», «и т. п.».
  rule("abbreviation", String.raw`${START}(?:и\s)?т\.\s?[едпн]\.`),
  // A number stays with the word it counts: «30 дней», «3 года».
  rule("number-word", String.raw`${START}\p{N}+\s(?=\p{Ll})`),
  // A one-letter preposition or conjunction does not end a line: «в целях», «с ограниченной».
  rule("short-word", String.raw`${START}[вксоуиаяВКСОУИАЯ]\s(?=[\p{L}\p{N}«"(])`),
  // A dash does not start a line: «далее — Оператор».
  rule("dash", String.raw`\s(?=[—–]\s)`),
];
