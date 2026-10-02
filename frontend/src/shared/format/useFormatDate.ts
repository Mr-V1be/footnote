"use client";

import { useFormatter, useNow } from "next-intl";
import { useCallback } from "react";

const RECENT_MS = 6 * 24 * 60 * 60 * 1000;
const NOW_REFRESH_MS = 60_000;

/** Recent moments read as relative time, older ones as a date. */
export function useFormatDate(): (iso: string) => string {
  const format = useFormatter();
  const now = useNow({ updateInterval: NOW_REFRESH_MS });
  return useCallback(
    (iso: string) => {
      const date = new Date(iso);
      return now.getTime() - date.getTime() < RECENT_MS
        ? format.relativeTime(date, now)
        : format.dateTime(date, { day: "numeric", month: "short", year: "numeric" });
    },
    [format, now],
  );
}
