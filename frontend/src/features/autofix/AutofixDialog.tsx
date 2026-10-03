"use client";

import { IconCircleCheck, IconHandStop, IconWand } from "@tabler/icons-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { usePathname, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";

import { queryKeys } from "@/features/documents/queries";
import { useApi } from "@/shared/api/ApiProvider";
import type { CheckDefinition } from "@/shared/api/types";
import { useErrorText } from "@/shared/i18n/useErrorText";
import { Button } from "@/shared/ui/button/Button";
import { DataList, DataRow } from "@/shared/ui/data-list/DataList";
import { Dialog, DialogClose, DialogContent } from "@/shared/ui/dialog/Dialog";
import { Form, FormError } from "@/shared/ui/form/Form";
import { Section } from "@/shared/ui/section/Section";
import { Skeleton } from "@/shared/ui/skeleton/Skeleton";
import { StatePanel } from "@/shared/ui/state-panel/StatePanel";
import { useToast } from "@/shared/ui/toast/Toast";

import { applyAutofix } from "./queries";
import { useAutofixPreview } from "./useAutofixPreview";

/**
 * What an automatic correction of the formatting would do, and doing it:
 * the corrected file becomes a new version, the original stays as it is.
 */
export function AutofixDialog({
  organization,
  documentId,
  version,
  checks,
  open,
  onOpenChange,
}: {
  organization: string;
  documentId: string;
  version: number;
  checks: readonly CheckDefinition[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {open ? (
        <AutofixContent
          organization={organization}
          documentId={documentId}
          version={version}
          checks={checks}
          onDone={() => onOpenChange(false)}
        />
      ) : null}
    </Dialog>
  );
}

function AutofixContent({
  organization,
  documentId,
  version,
  checks,
  onDone,
}: {
  organization: string;
  documentId: string;
  version: number;
  checks: readonly CheckDefinition[];
  onDone: () => void;
}) {
  const t = useTranslations("autofix");
  const tc = useTranslations("common");
  const api = useApi();
  const toast = useToast();
  const router = useRouter();
  const pathname = usePathname();
  const errorText = useErrorText();
  const queryClient = useQueryClient();
  const titles = new Map(checks.map((check) => [check.code, check.title]));
  const title = (code: string) => titles.get(code) ?? code;
  const preview = useAutofixPreview(organization, documentId, version, true);
  const apply = useMutation({
    mutationFn: () => applyAutofix(api, organization, documentId, version),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.documents(organization) });
      toast({
        tone: "success",
        title: t("applied", { number: result.version }),
        description: t("appliedDescription", { source: version }),
      });
      onDone();
      router.replace(`${pathname}?v=${result.version}`, { scroll: false });
    },
  });
  const planned = preview.data?.planned ?? [];

  function body() {
    if (preview.isPending) {
      return (
        <Form>
          <Skeleton width="60%" />
          <Skeleton shape="block" height="6rem" />
        </Form>
      );
    }
    if (preview.isError) {
      return <FormError>{errorText(preview.error)}</FormError>;
    }
    if (!preview.data.editable) {
      return <StatePanel icon={<IconHandStop stroke={1.75} />} title={t("notEditable")} />;
    }
    return (
      <Form>
        {planned.length > 0 ? (
          <Section title={t("planned")}>
            <DataList label={t("planned")}>
              {planned.map((item) => (
                <DataRow
                  key={item.checkCode}
                  leading={<IconCircleCheck stroke={1.75} />}
                  title={title(item.checkCode)}
                  aside={<span>{t("places", { count: item.places })}</span>}
                />
              ))}
            </DataList>
          </Section>
        ) : (
          <StatePanel icon={<IconHandStop stroke={1.75} />} title={t("nothingTitle")} />
        )}
        {preview.data.skipped.length > 0 ? (
          <Section title={t("skipped")}>
            <DataList label={t("skipped")}>
              {preview.data.skipped.map((item) => (
                <DataRow
                  key={item.checkCode}
                  leading={<IconHandStop stroke={1.75} />}
                  title={title(item.checkCode)}
                  description={<span>{t(`reasons.${item.reason}`)}</span>}
                />
              ))}
            </DataList>
          </Section>
        ) : null}
        {apply.isError ? <FormError>{errorText(apply.error)}</FormError> : null}
      </Form>
    );
  }

  return (
    <DialogContent
      title={t("title")}
      closeLabel={tc("close")}
      footer={
        <>
          <DialogClose asChild>
            <Button variant="secondary">{tc("cancel")}</Button>
          </DialogClose>
          <Button
            variant="primary"
            icon={<IconWand stroke={1.75} />}
            disabled={planned.length === 0}
            loading={apply.isPending}
            onClick={() => apply.mutate()}
          >
            {t("apply")}
          </Button>
        </>
      }
    >
      {body()}
    </DialogContent>
  );
}
