"use client";

import { IconAlertTriangle, IconCircleCheck, IconInfoCircle } from "@tabler/icons-react";
import { Toast as Primitive } from "radix-ui";
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

import styles from "./toast.module.css";

export type ToastTone = "success" | "critical" | "info";

interface ToastMessage {
  id: number;
  tone: ToastTone;
  title: string;
  description?: string;
}

type Show = (message: Omit<ToastMessage, "id">) => void;

const ToastContext = createContext<Show | null>(null);
const TOAST_DURATION_MS = 5000;
const ICONS: Record<ToastTone, ReactNode> = {
  success: <IconCircleCheck stroke={1.75} />,
  critical: <IconAlertTriangle stroke={1.75} />,
  info: <IconInfoCircle stroke={1.75} />,
};

let nextId = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [messages, setMessages] = useState<ToastMessage[]>([]);
  const show = useCallback<Show>((message) => {
    nextId += 1;
    setMessages((current) => [...current, { ...message, id: nextId }]);
  }, []);
  const value = useMemo(() => show, [show]);
  return (
    <ToastContext value={value}>
      <Primitive.Provider duration={TOAST_DURATION_MS} swipeDirection="down">
        {children}
        {messages.map((message) => (
          <Primitive.Root
            key={message.id}
            className={`${styles.toast} ${styles[message.tone]}`}
            onOpenChange={(open) => {
              if (!open) setMessages((current) => current.filter((item) => item.id !== message.id));
            }}
          >
            <span className={styles.icon} aria-hidden>
              {ICONS[message.tone]}
            </span>
            <div className={styles.text}>
              <Primitive.Title className={styles.title}>{message.title}</Primitive.Title>
              {message.description ? (
                <Primitive.Description className={styles.description}>
                  {message.description}
                </Primitive.Description>
              ) : null}
            </div>
          </Primitive.Root>
        ))}
        <Primitive.Viewport className={styles.viewport} />
      </Primitive.Provider>
    </ToastContext>
  );
}

export function useToast(): Show {
  const show = useContext(ToastContext);
  if (!show) throw new Error("useToast must be used inside ToastProvider");
  return show;
}
