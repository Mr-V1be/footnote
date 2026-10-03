"use client";

import { IconHistory, IconMessageQuestion, IconPlus } from "@tabler/icons-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";

import { LoadFailure } from "@/features/access/LoadFailure";
import { useOrganizationAlias } from "@/features/organization/hooks";
import { useApi } from "@/shared/api/ApiProvider";
import { ApiError } from "@/shared/api/errors";
import type { Conversation } from "@/shared/api/types";
import { useMediaQuery } from "@/shared/hooks/useMediaQuery";
import { useErrorText } from "@/shared/i18n/useErrorText";
import { Button } from "@/shared/ui/button/Button";
import { Drawer, DrawerContent } from "@/shared/ui/drawer/Drawer";
import { FormError } from "@/shared/ui/form/Form";
import { IconButton } from "@/shared/ui/icon-button/IconButton";
import { Skeleton } from "@/shared/ui/skeleton/Skeleton";
import { StatePanel } from "@/shared/ui/state-panel/StatePanel";

import styles from "./ask.module.css";
import { AskUnavailable, type UnavailableReason } from "./AskUnavailable";
import { Composer } from "./Composer";
import { ConversationList } from "./ConversationList";
import { ConversationView } from "./ConversationView";
import {
  askKeys,
  askQuestion,
  fetchAskStatus,
  fetchConversation,
  fetchConversations,
} from "./queries";

/** Where questions to the norm cannot be answered by the stand right now. */
function unavailableReason(error: unknown): UnavailableReason | null {
  if (!(error instanceof ApiError)) return null;
  if (error.code === "model_not_configured") return "model";
  if (error.code === "model_daily_limit") return "limit";
  if (error.code === "corpus_not_indexed") return "index";
  return null;
}

/**
 * Questions to the corpus of norms. An answer stands only on quotes from the
 * law with references to its provisions; without them it says so.
 */
export function AskScreen({ conversationId }: { conversationId: string | null }) {
  const t = useTranslations("ask");
  const tc = useTranslations("common");
  const api = useApi();
  const router = useRouter();
  const errorText = useErrorText();
  const queryClient = useQueryClient();
  const organization = useOrganizationAlias();
  const wide = useMediaQuery("(width >= 64rem)");
  const [historyOpen, setHistoryOpen] = useState(false);
  const end = useRef<HTMLDivElement>(null);

  const status = useQuery({
    queryKey: askKeys.status(organization),
    queryFn: () => fetchAskStatus(api, organization),
  });
  const conversations = useQuery({
    queryKey: askKeys.conversations(organization),
    queryFn: () => fetchConversations(api, organization),
  });
  const conversation = useQuery({
    queryKey: askKeys.conversation(organization, conversationId ?? ""),
    queryFn: () => fetchConversation(api, organization, conversationId ?? ""),
    enabled: conversationId !== null,
  });
  const ask = useMutation({
    mutationFn: (question: string) => askQuestion(api, organization, question, conversationId),
    onSuccess: (saved: Conversation) => {
      queryClient.setQueryData(askKeys.conversation(organization, saved.id), saved);
      void queryClient.invalidateQueries({ queryKey: askKeys.conversations(organization) });
      if (saved.id !== conversationId) router.replace(`/o/${organization}/ask/${saved.id}`);
    },
  });
  const turns = conversation.data?.turns ?? [];
  const pending = ask.isPending ? ask.variables : null;
  const unavailable: UnavailableReason | null =
    status.data && !status.data.configured
      ? "model"
      : status.data?.requestsLeftToday === 0
        ? "limit"
        : unavailableReason(ask.error);

  // A new question or answer comes into view at the bottom.
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns.length, pending]);

  const history = (
    <ConversationList
      organization={organization}
      conversations={conversations.data}
      currentId={conversationId}
      onNavigate={() => setHistoryOpen(false)}
    />
  );

  function body() {
    if (status.isPending || (conversationId && conversation.isPending)) {
      return (
        <div className={styles.turns} aria-busy>
          <Skeleton width="60%" height="1.5rem" />
          <Skeleton shape="block" height="8rem" />
        </div>
      );
    }
    if (status.isError) {
      return <LoadFailure error={status.error} onRetry={() => void status.refetch()} />;
    }
    if (conversation.isError) {
      return <LoadFailure error={conversation.error} onRetry={() => void conversation.refetch()} />;
    }
    if (unavailable && turns.length === 0) return <AskUnavailable reason={unavailable} />;
    if (turns.length === 0 && !pending) {
      return (
        <StatePanel
          icon={<IconMessageQuestion stroke={1.75} />}
          title={t("emptyTitle")}
          description={t("emptyDescription")}
        />
      );
    }
    return <ConversationView turns={turns} pendingQuestion={pending ?? null} />;
  }

  return (
    <div className={styles.layout}>
      {wide ? (
        <aside className={styles.historyColumn} aria-label={t("history")}>
          <Button asChild variant="secondary" block icon={<IconPlus stroke={1.75} />}>
            <Link href={`/o/${organization}/ask`}>{t("newConversation")}</Link>
          </Button>
          {history}
        </aside>
      ) : null}
      <section className={styles.chat} aria-label={conversation.data?.title ?? t("title")}>
        <header className={styles.chatHeader}>
          <h1 className={styles.chatTitle}>{conversation.data?.title ?? t("title")}</h1>
          {wide ? null : (
            <div className={styles.chatActions}>
              <IconButton
                label={t("history")}
                icon={<IconHistory stroke={1.75} />}
                variant="secondary"
                onClick={() => setHistoryOpen(true)}
              />
              {conversationId ? (
                <Button asChild variant="secondary" icon={<IconPlus stroke={1.75} />}>
                  <Link href={`/o/${organization}/ask`}>{t("newShort")}</Link>
                </Button>
              ) : null}
            </div>
          )}
        </header>
        {body()}
        {ask.isError && !unavailableReason(ask.error) ? (
          <FormError>{errorText(ask.error)}</FormError>
        ) : null}
        {unavailable && turns.length > 0 ? <AskUnavailable reason={unavailable} /> : null}
        <div ref={end} />
        {status.data?.configured && unavailable !== "index" && unavailable !== "limit" ? (
          <Composer busy={ask.isPending} onAsk={(question) => ask.mutate(question)} />
        ) : null}
      </section>
      <Drawer open={historyOpen} onOpenChange={setHistoryOpen}>
        <DrawerContent side="bottom" title={t("history")} closeLabel={tc("close")}>
          {history}
        </DrawerContent>
      </Drawer>
    </div>
  );
}
