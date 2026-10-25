"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NextIntlClientProvider, type AbstractIntlMessages } from "next-intl";
import { useState, type ReactNode } from "react";

import { ApiProvider } from "@/shared/api/ApiProvider";
import type { Locale } from "@/shared/i18n/locales";
import { TIME_ZONE } from "@/shared/i18n/time";
import { ThemeProvider } from "@/shared/theme/ThemeContext";
import type { ThemePreference } from "@/shared/theme/theme";
import { ToastProvider } from "@/shared/ui/toast/Toast";
import { TooltipProvider } from "@/shared/ui/tooltip/Tooltip";

const STALE_TIME_MS = 15_000;

export function AppProviders({
  locale,
  messages,
  now,
  theme,
  children,
}: {
  locale: Locale;
  messages: AbstractIntlMessages;
  /** The server's clock, so relative times render the same on both sides. */
  now: Date;
  theme: ThemePreference;
  children: ReactNode;
}) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: STALE_TIME_MS, refetchOnWindowFocus: true, retry: 1 },
        },
      }),
  );
  return (
    <NextIntlClientProvider locale={locale} messages={messages} now={now} timeZone={TIME_ZONE}>
      <QueryClientProvider client={queryClient}>
        <ApiProvider>
          <ThemeProvider initial={theme}>
            <TooltipProvider>
              <ToastProvider>{children}</ToastProvider>
            </TooltipProvider>
          </ThemeProvider>
        </ApiProvider>
      </QueryClientProvider>
    </NextIntlClientProvider>
  );
}
