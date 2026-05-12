"use client";

import { useState } from "react";
import { Download, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { ApiClientError } from "@shared/lib/api-client";
import { downloadFileUrl } from "@shared/lib/paysync-api";
import { cn } from "@shared/lib/format";

export interface FileDownloadButtonProps {
  fileId: string;
  fileLabel: string;
  sha256?: string;
  sizeBytes?: number;
  className?: string;
}

export function FileDownloadButton({
  fileId, fileLabel, sha256, sizeBytes, className,
}: FileDownloadButtonProps) {
  const [busy, setBusy] = useState(false);

  async function handleClick() {
    setBusy(true);
    try {
      const { url } = await downloadFileUrl(fileId);
      window.location.href = url;
    } catch (e) {
      const msg = e instanceof ApiClientError
        ? `${e.code}: ${e.message}` : String(e);
      toast.error(`Download failed — ${msg}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <button
        type="button" onClick={handleClick} disabled={busy}
        className="inline-flex items-center gap-1.5 self-start rounded-md border bg-background px-3 py-1.5 text-sm hover:bg-muted disabled:opacity-50"
      >
        {busy
          ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
          : <Download className="h-3.5 w-3.5" />}
        {fileLabel}
      </button>
      {(sha256 || sizeBytes != null) && (
        <p className="font-mono text-[10px] text-muted-foreground">
          {sizeBytes != null && `${formatBytes(sizeBytes)} · `}
          {sha256 && `sha256: ${sha256.slice(0, 12)}…${sha256.slice(-4)}`}
        </p>
      )}
    </div>
  );
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}
