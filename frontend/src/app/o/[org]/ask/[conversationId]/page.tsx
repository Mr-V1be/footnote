import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { AskScreen } from "@/features/ask/AskScreen";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("ask"))("title") };
}

export default async function ConversationPage({
  params,
}: {
  params: Promise<{ conversationId: string }>;
}) {
  const { conversationId } = await params;
  return <AskScreen conversationId={conversationId} />;
}
