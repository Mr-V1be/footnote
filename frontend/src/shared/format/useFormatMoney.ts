"use client";

import { useFormatter } from "next-intl";
import { useCallback } from "react";

const KOPECKS_IN_RUBLE = 100;

/** An amount in kopecks (minor units) as money: "4 900 ₽", "4 900,50 ₽". */
export function useFormatMoney(): (kopecks: number, currency?: string) => string {
  const format = useFormatter();
  return useCallback(
    (kopecks: number, currency = "RUB") =>
      format.number(kopecks / KOPECKS_IN_RUBLE, {
        style: "currency",
        currency,
        minimumFractionDigits: kopecks % KOPECKS_IN_RUBLE === 0 ? 0 : 2,
        maximumFractionDigits: 2,
      }),
    [format],
  );
}
