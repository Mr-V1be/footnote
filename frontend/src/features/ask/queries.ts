import type { ApiClient } from "@/shared/api/client";
import { unwrap } from "@/shared/api/errors";
import type { AskStatus, Conversation, ConversationSummary } from "@/shared/api/types";

export const askKeys = {
  all: (organization: string) => ["organizations", organization, "ask"] as const,
  status: (organization: string) => [...askKeys.all(organization), "status"] as const,
  conversations: (organization: string) => [...askKeys.all(organization), "conversations"] as const,
  conversation: (organization: string, id: string) =>
    [...askKeys.conversations(organization), id] as const,
};

const org = (organization: string) => ({ params: { path: { organization } } });

export async function fetchAskStatus(api: ApiClient, organization: string): Promise<AskStatus> {
  return unwrap(
    await api.GET("/api/v1/organizations/{organization}/ask/status", org(organization)),
  );
}

export async function fetchConversations(
  api: ApiClient,
  organization: string,
): Promise<ConversationSummary[]> {
  return unwrap(
    await api.GET("/api/v1/organizations/{organization}/ask/conversations", org(organization)),
  );
}

export async function fetchConversation(
  api: ApiClient,
  organization: string,
  id: string,
): Promise<Conversation> {
  return unwrap(
    await api.GET("/api/v1/organizations/{organization}/ask/conversations/{conversation_id}", {
      params: { path: { organization, conversation_id: id } },
    }),
  );
}

export async function askQuestion(
  api: ApiClient,
  organization: string,
  question: string,
  conversationId: string | null,
): Promise<Conversation> {
  return unwrap(
    await api.POST("/api/v1/organizations/{organization}/ask", {
      ...org(organization),
      body: { question, conversationId },
    }),
  );
}

/** An answer's text and its footnote markers ("[2]") in reading order. */
export type AnswerPart = { type: "text"; text: string } | { type: "marker"; number: number };

export function answerParts(answer: string): AnswerPart[] {
  const parts: AnswerPart[] = [];
  let last = 0;
  for (const match of answer.matchAll(/\[(\d+)\]/g)) {
    const index = match.index;
    // A marker sits on the word it supports: the space before it goes.
    const text = answer.slice(last, index).trimEnd();
    if (text) parts.push({ type: "text", text });
    parts.push({ type: "marker", number: Number(match[1]) });
    last = index + match[0].length;
  }
  if (last < answer.length) parts.push({ type: "text", text: answer.slice(last) });
  return parts;
}
