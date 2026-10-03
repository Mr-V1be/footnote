"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { useDebouncedValue } from "@/shared/hooks/useDebouncedValue";
import { useReplaceParams } from "@/shared/hooks/useReplaceParams";

import type { DocumentFilters } from "../queries";

const SEARCH_DEBOUNCE_MS = 250;

/**
 * Filters live in the address. The search box updates immediately; the
 * address follows when typing pauses.
 */
export function useListFilters(): {
  search: string;
  setSearch: (value: string) => void;
  kind: string | null;
  setKind: (value: string | null) => void;
  applied: DocumentFilters;
  reset: () => void;
} {
  const params = useSearchParams();
  const kind = params.get("kind");
  const [search, setSearch] = useState(params.get("q") ?? "");
  const debounced = useDebouncedValue(search.trim(), SEARCH_DEBOUNCE_MS);

  const replace = useReplaceParams();

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
