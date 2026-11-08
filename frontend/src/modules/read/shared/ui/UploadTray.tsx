import { randomUUID } from "@/shared/lib";
import { useEffect, useRef, useState } from "react";
import { ClipboardPaste, ImagePlus } from "lucide-react";
import type { ImportStatus } from "../importStatus";
import { CollectProgress } from "./CollectProgress";

interface UploadTrayProps {
  /** Called with `{id, file}` pairs in the order chosen — the id lets the caller
   *  report per-file `uploadStatus` back via the same key. */
  onConfirm: (items: { id: string; file: File }[]) => Promise<void> | void;
  busy: boolean;
  /** Per-file status while `busy`, keyed by the id passed to `onConfirm`. */
  uploadStatus?: Record<string, ImportStatus>;
}

/** Choose local files — or paste images from the clipboard (Ctrl/⌘+V while this
 *  tab is showing, or the "Paste" button) — and they go straight into the pool
 *  (bytes direct to Storage, see the upload features). No staging step: the pool
 *  is where images are picked and ordered. */
export function UploadTray({ onConfirm, busy, uploadStatus }: UploadTrayProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [pasteNote, setPasteNote] = useState<string | null>(null);

  const upload = async (files: Iterable<File> | ArrayLike<File> | null) => {
    if (!files) return;
    const images = Array.from(files).filter((f) => f.type.startsWith("image/"));
    if (images.length === 0) return;
    await onConfirm(images.map((file) => ({ id: randomUUID(), file })));
  };

  // Ctrl/⌘+V anywhere while this tab is mounted. Works on plain-http pages too
  // (unlike the async Clipboard API the button uses). Pastes into text fields
  // are left alone.
  const uploadRef = useRef(upload);
  useEffect(() => {
    uploadRef.current = upload;
  });
  useEffect(() => {
    const onPaste = (event: ClipboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target?.closest("input, textarea, [contenteditable='true']")) return;
      const files = Array.from(event.clipboardData?.files ?? []).filter((f) => f.type.startsWith("image/"));
      if (files.length === 0) return;
      event.preventDefault();
      setPasteNote(null);
      void uploadRef.current(files);
    };
    document.addEventListener("paste", onPaste);
    return () => document.removeEventListener("paste", onPaste);
  }, []);

  const pasteFromButton = async () => {
    setPasteNote(null);
    if (!navigator.clipboard?.read) {
      setPasteNote("This browser can't read the clipboard from a button here — press Ctrl+V (⌘V) instead.");
      return;
    }
    try {
      const items = await navigator.clipboard.read();
      const files: File[] = [];
      for (const item of items) {
        const type = item.types.find((t) => t.startsWith("image/"));
        if (!type) continue;
        const blob = await item.getType(type);
        files.push(new File([blob], `pasted-${Date.now()}.${type.split("/")[1] ?? "png"}`, { type }));
      }
      if (files.length === 0) {
        setPasteNote("No image on the clipboard.");
        return;
      }
      await upload(files);
    } catch {
      setPasteNote("Couldn't read the clipboard (permission denied?) — press Ctrl+V (⌘V) instead.");
    }
  };

  return (
    <div className="flex flex-col gap-3">
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        multiple
        className="hidden"
        onChange={(e) => {
          void upload(e.target.files);
          e.target.value = ""; // allow re-picking the same files
        }}
      />

      <div className="flex flex-wrap gap-2">
      <button
        onClick={() => inputRef.current?.click()}
        disabled={busy}
        className="flex w-fit items-center gap-1.5 rounded-md border border-[var(--owl-border)] px-3 py-1.5 text-sm text-[var(--owl-brown)] hover:bg-[var(--owl-brown-mid)]/10 transition-colors cursor-pointer disabled:opacity-50"
      >
        <ImagePlus size={15} aria-hidden="true" />
        {busy ? "Uploading…" : "Choose images"}
      </button>
      <button
        onClick={pasteFromButton}
        disabled={busy}
        className="flex w-fit items-center gap-1.5 rounded-md border border-[var(--owl-border)] px-3 py-1.5 text-sm text-[var(--owl-brown)] hover:bg-[var(--owl-brown-mid)]/10 transition-colors cursor-pointer disabled:opacity-50"
      >
        <ClipboardPaste size={15} aria-hidden="true" />
        Paste from clipboard
      </button>
      </div>
      <p className="text-xs text-[var(--owl-brown-muted)]">Tip: copy an image anywhere, then press Ctrl+V (⌘V) here.</p>
      {pasteNote && <p className="text-sm text-[var(--owl-brown-muted)]">{pasteNote}</p>}

      {busy && <CollectProgress status={uploadStatus} />}
    </div>
  );
}
