import type { Metadata, Viewport } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans, Literata } from "next/font/google";
import { cookies } from "next/headers";
import { getLocale, getMessages, getNow, getTranslations } from "next-intl/server";
import type { ReactNode } from "react";

import { AppProviders } from "@/features/session/AppProviders";
import { parseTheme, THEME_COOKIE, themeAttribute } from "@/shared/theme/theme";

import "./globals.css";

const sans = IBM_Plex_Sans({
  subsets: ["latin", "cyrillic"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-plex-sans",
  display: "swap",
});
const mono = IBM_Plex_Mono({
  subsets: ["latin", "cyrillic"],
  weight: ["400", "500"],
  variable: "--font-plex-mono",
  display: "swap",
});
const serif = Literata({
  subsets: ["latin", "cyrillic"],
  style: ["normal", "italic"],
  variable: "--font-literata",
  display: "swap",
});

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("app");
  return {
    title: { default: t("name"), template: `%s — ${t("name")}` },
    description: t("description"),
  };
}

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f6f6f3" },
    { media: "(prefers-color-scheme: dark)", color: "#131518" },
  ],
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  const theme = parseTheme((await cookies()).get(THEME_COOKIE)?.value);
  const locale = await getLocale();
  return (
    <html
      lang={locale}
      data-theme={themeAttribute(theme)}
      className={`${sans.variable} ${mono.variable} ${serif.variable}`}
    >
      <body>
        <AppProviders
          locale={locale}
          messages={await getMessages()}
          now={await getNow()}
          theme={theme}
        >
          {children}
        </AppProviders>
      </body>
    </html>
  );
}
