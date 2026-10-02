import type { UploadResult } from "@/shared/api/types";

export type UploadOutcome =
  { ok: true; result: UploadResult } | { ok: false; code: string; status: number };

/**
 * Sends a file with upload progress (fetch exposes no upload progress).
 * The idempotency key makes a retried request return the first outcome.
 */
export function sendUpload({
  url,
  form,
  idempotencyKey,
  onProgress,
  signal,
}: {
  url: string;
  form: FormData;
  idempotencyKey: string;
  onProgress: (fraction: number) => void;
  signal: AbortSignal;
}): Promise<UploadOutcome> {
  return new Promise((resolve) => {
    const request = new XMLHttpRequest();
    request.open("POST", url);
    request.setRequestHeader("Idempotency-Key", idempotencyKey);
    request.setRequestHeader("Accept", "application/json");
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(event.loaded / event.total);
    };
    request.onload = () => {
      let body: unknown = null;
      try {
        body = JSON.parse(request.responseText);
      } catch {
        body = null;
      }
      if (request.status >= 200 && request.status < 300) {
        resolve({ ok: true, result: body as UploadResult });
        return;
      }
      const code =
        typeof body === "object" && body !== null && "code" in body && typeof body.code === "string"
          ? body.code
          : "unexpected";
      resolve({ ok: false, code, status: request.status });
    };
    request.onerror = () => resolve({ ok: false, code: "network", status: 0 });
    signal.addEventListener("abort", () => request.abort());
    request.send(form);
  });
}
