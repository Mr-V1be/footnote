"use client";

import { usePathname, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { useDebouncedValue } from "@/shared/hooks/useDebouncedValue";

import type { DocumentFilters } from "../queries";

const SEARCH_DEBOUNCE_MS = 250;

/**
 * Filters live in the address so that reload, back and shared links keep
 * them. The search box updates immediately; the address follows when typing
 * pauses. The address is replaced in the browser only: the list query runs
 * on the client and the page is not rendered again on the server.
 */
export function useListFilters(): {
  search: string;
  setSearch: (value: string) => void;
  kind: string | null;
  setKind: (value: string | null) => void;
  applied: DocumentFilters;
  reset: () => void;
} {
  const pathname = usePathname();
  const params = useSearchParams();
  const kind = params.get("kind");
  const [search, setSearch] = useState(params.get("q") ?? "");
  const debounced = useDebouncedValue(search.trim(), SEARCH_DEBOUNCE_MS);

  const replace = useCallback(
    (next: Record<string, string | null>) => {
      const query = new URLSearchParams(params.toString());
      for (const [key, value] of Object.entries(next)) {
        if (value) query.set(key, value);
        else query.delete(key);
      }
      const suffix = query.toString();
      window.history.replaceState(null, "", suffix ? `${pathname}?${suffix}` : pathname);
    },
    [params, pathname],
  );

  useEffect(() => {
    if ((params.get("q") ?? "") !== debounced) replace({ q: debounced || null });
  }, [debounced, params, replace]);

  return {
    search,
    setSearch,
    kind,
    setKind: (value) => replace({ kind: value }),
    applied: { search: debounced, kind },
    reset: () => {
      setSearch("");
      replace({ q: null, kind: null });
    },
  };
}
