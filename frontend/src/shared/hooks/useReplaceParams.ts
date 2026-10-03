"use client";

import { usePathname, useSearchParams } from "next/navigation";
import { useCallback } from "react";

/**
 * Updates parameters of the address in the browser only (no navigation, no
 * server render): filters survive reload, back and shared links. A null
 * value removes the parameter.
 */
export function useReplaceParams(): (next: Record<string, string | null>) => void {
  const pathname = usePathname();
  const params = useSearchParams();
  return useCallback(
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
}
