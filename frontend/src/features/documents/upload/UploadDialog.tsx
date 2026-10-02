"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useEffect, useMemo, useRef, useState } from "react";

import { useMembership } from "@/features/session/membership";
import { BFF_PREFIX } from "@/shared/api/client";
import { useApi } from "@/shared/api/ApiProvider";
import type { Catalog, UploadResult } from "@/shared/api/types";
import { useFormatBytes } from "@/shared/format/useFormatBytes";
import { useCodeLabel } from "@/shared/i18n/useCodeLabel";
import { Button } from "@/shared/ui/button/Button";
import { Dialog, DialogContent } from "@/shared/ui/dialog/Dialog";
import { Dropzone } from "@/shared/ui/dropzone/Dropzone";
import { Field, TextInput } from "@/shared/ui/field/Field";
import { ProgressBar } from "@/shared/ui/progress/ProgressBar";
import { Select } from "@/shared/ui/select/Select";
import { useToast } from "@/shared/ui/toast/Toast";

import { FileTypeIcon } from "../FileTypeIcon";
import { fetchCatalog, queryKeys } from "../queries";
import styles from "./upload.module.css";
import { sendUpload } from "./uploadRequest";

export type UploadTarget =
  { type: "document"; workspace: string } | { type: "version"; documentId: string };

const UPLOAD_ERRORS = [
  "unsupported_format",
  "file_too_large",
  "version_unchanged",
  "missing_permission",
  "network",
] as const;
type UploadErrorCode = (typeof UPLOAD_ERRORS)[number] | "unexpected";

function uploadError(code: string): UploadErrorCode {
  return UPLOAD_ERRORS.find((known) => known === code) ?? "unexpected";
}

function extensionOf(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot === -1 ? "" : name.slice(dot).toLowerCase();
}

function formatOf(catalog: Catalog, file: File): string | null {
  return (
    catalog.formats.find((format) => format.extensions.includes(extensionOf(file.name)))?.code ??
    null
  );
}

export function UploadDialog({
  target,
  open,
  onOpenChange,
  onUploaded,
}: {
  target: UploadTarget;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onUploaded?: (result: UploadResult) => void;
}) {
  const [busy, setBusy] = useState(false);
  return (
    <Dialog open={open} onOpenChange={(next) => !busy && onOpenChange(next)}>
      {/* Mounted only while open, so every opening starts with a clean form. */}
      {open ? (
        <UploadForm
          target={target}
          onBusyChange={setBusy}
          onCancel={() => onOpenChange(false)}
          onUploaded={(result) => {
            onUploaded?.(result);
            onOpenChange(false);
          }}
        />
      ) : null}
    </Dialog>
  );
}

function UploadForm({
  target,
  onBusyChange,
  onCancel,
  onUploaded,
}: {
  target: UploadTarget;
  onBusyChange: (busy: boolean) => void;
  onCancel: () => void;
  onUploaded: (result: UploadResult) => void;
}) {
  const t = useTranslations("upload");
  const tc = useTranslations("common");
  const api = useApi();
  const toast = useToast();
  const queryClient = useQueryClient();
  const kindLabel = useCodeLabel("kinds");
  const formatBytes = useFormatBytes();
  const organization = useMembership().membership.organization.alias;
  const catalog = useQuery({
    queryKey: queryKeys.catalog(),
    queryFn: () => fetchCatalog(api),
    staleTime: Infinity,
  });

  const [file, setFile] = useState<File | null>(null);
  const [kind, setKind] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const idempotencyKey = useRef("");
  const abort = useRef<AbortController | null>(null);

  useEffect(() => () => abort.current?.abort(), []);

  const maxSize = catalog.data ? formatBytes(catalog.data.maxUploadBytes) : "";
  const accept = useMemo(
    () => catalog.data?.formats.flatMap((format) => format.extensions).join(",") ?? "",
    [catalog.data],
  );
  const defaultKind = catalog.data?.kinds.find((item) => item.isDefault)?.code ?? "";
  const selectedKind = kind ?? defaultKind;

  function choose(next: File) {
    setError(null);
    if (catalog.data && !formatOf(catalog.data, next)) {
      setError(t("errors.unsupported_format"));
      return;
    }
    if (catalog.data && next.size > catalog.data.maxUploadBytes) {
      setError(t("errors.file_too_large", { size: maxSize }));
      return;
    }
    idempotencyKey.current = crypto.randomUUID();
    setFile(next);
  }

  async function submit() {
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    if (target.type === "document") {
      if (selectedKind) form.append("kind", selectedKind);
      if (title.trim()) form.append("title", title.trim());
    }
    const url =
      target.type === "document"
        ? `${BFF_PREFIX}/api/v1/organizations/${organization}/workspaces/${target.workspace}/documents`
        : `${BFF_PREFIX}/api/v1/organizations/${organization}/documents/${target.documentId}/versions`;
    abort.current = new AbortController();
    setError(null);
    setProgress(0);
    onBusyChange(true);
    const outcome = await sendUpload({
      url,
      form,
      idempotencyKey: idempotencyKey.current,
      onProgress: setProgress,
      signal: abort.current.signal,
    });
    onBusyChange(false);
    setProgress(null);
    if (!outcome.ok) {
      setError(t(`errors.${uploadError(outcome.code)}`, { size: maxSize }));
      return;
    }
    await queryClient.invalidateQueries({ queryKey: queryKeys.documents(organization) });
    toast(
      target.type === "document"
        ? { tone: "success", title: t("done"), description: t("doneDescription") }
        : { tone: "success", title: t("versionDone", { number: outcome.result.versionNumber }) },
    );
    onUploaded(outcome.result);
  }

  const uploading = progress !== null;
  const detected = file && catalog.data ? formatOf(catalog.data, file) : null;
  return (
    <DialogContent
      title={target.type === "document" ? t("title") : t("versionTitle")}
      description={target.type === "document" ? t("description") : t("versionDescription")}
      closeLabel={tc("close")}
      footer={
        <>
          <Button variant="secondary" onClick={onCancel} disabled={uploading}>
            {tc("cancel")}
          </Button>
          <Button
            variant="primary"
            onClick={() => void submit()}
            disabled={!file}
            loading={uploading}
          >
            {t("submit")}
          </Button>
        </>
      }
    >
      <div className={styles.form}>
        {file ? (
          <div className={styles.file}>
            <FileTypeIcon format={detected ?? ""} className={styles.fileIcon} />
            <div className={styles.fileText}>
              <span className={styles.fileName}>{file.name}</span>
              <span className={styles.fileSize}>{formatBytes(file.size)}</span>
            </div>
            <Button variant="ghost" size="sm" onClick={() => setFile(null)} disabled={uploading}>
              {t("selectAnother")}
            </Button>
          </div>
        ) : (
          <Dropzone
            accept={accept}
            title={t("dropTitle")}
            hint={t("dropHint", { size: maxSize })}
            onFile={choose}
          />
        )}
        {uploading ? <ProgressBar value={progress ?? undefined} label={t("uploading")} /> : null}
        {error ? (
          <p className={styles.error} role="alert">
            {error}
          </p>
        ) : null}
        {target.type === "document" && catalog.data ? (
          <div className={styles.fields}>
            <Field label={t("kind")}>
              {({ id }) => (
                <Select
                  id={id}
                  block
                  value={selectedKind}
                  onValueChange={setKind}
                  options={catalog.data.kinds.map((item) => ({
                    value: item.code,
                    label: kindLabel(item.code),
                  }))}
                />
              )}
            </Field>
            <Field label={t("titleLabel")} hint={t("titleHint")}>
              {({ id, describedBy }) => (
                <TextInput
                  id={id}
                  aria-describedby={describedBy}
                  value={title}
                  maxLength={300}
                  placeholder={file?.name.replace(/\.[^.]+$/, "")}
                  onChange={(event) => setTitle(event.target.value)}
                />
              )}
            </Field>
          </div>
        ) : null}
      </div>
    </DialogContent>
  );
}
