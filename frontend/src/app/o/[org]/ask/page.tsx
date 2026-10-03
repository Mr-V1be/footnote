import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { AskScreen } from "@/features/ask/AskScreen";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("ask"))("title") };
}

export default function AskPage() {
  return <AskScreen conversationId={null} />;
}
