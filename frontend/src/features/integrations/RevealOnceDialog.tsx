"use client";

import { IconEyeOff } from "@tabler/icons-react";
import { useTranslations } from "next-intl";

import { Button } from "@/shared/ui/button/Button";
import { CopyField } from "@/shared/ui/copy-field/CopyField";
import { Dialog, DialogClose, DialogContent } from "@/shared/ui/dialog/Dialog";
import { Form } from "@/shared/ui/form/Form";
import { Notice } from "@/shared/ui/notice/Notice";

/**
 * A secret the server shows once (a key's token, a webhook's signing
 * secret): copy it now, it is not kept in readable form.
 */
export function RevealOnceDialog({
  secret,
  title,
  label,
  onClose,
}: {
  /** The secret to show; null keeps the dialog closed. */
  secret: string | null;
  title: string;
  label: string;
  onClose: () => void;
}) {
  const t = useTranslations("integrations");
  const tc = useTranslations("common");
  return (
    <Dialog open={secret !== null} onOpenChange={(open) => !open && onClose()}>
      {secret !== null ? (
        <DialogContent
          title={title}
          closeLabel={tc("close")}
          footer={
            <DialogClose asChild>
              <Button variant="primary">{t("secretSaved")}</Button>
            </DialogClose>
          }
        >
          <Form>
            <Notice icon={<IconEyeOff stroke={1.75} />} tone="warning">
              {t("shownOnce")}
            </Notice>
            <CopyField
              label={label}
              value={secret}
              copyLabel={t("copy")}
              copiedLabel={t("copied")}
            />
          </Form>
        </DialogContent>
      ) : null}
    </Dialog>
  );
}
