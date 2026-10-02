const KILOBYTE = 1024;
const MEGABYTE = KILOBYTE * 1024;

export type BytesUnit = "bytes" | "kilobytes" | "megabytes";

/** Splits a size into a value and the unit its label should use. */
export function bytesParts(bytes: number, locale: string): { unit: BytesUnit; value: string } {
  const number = new Intl.NumberFormat(locale, { maximumFractionDigits: 1 });
  if (bytes >= MEGABYTE) return { unit: "megabytes", value: number.format(bytes / MEGABYTE) };
  if (bytes >= KILOBYTE)
    return { unit: "kilobytes", value: number.format(Math.round(bytes / KILOBYTE)) };
  return { unit: "bytes", value: number.format(bytes) };
}
