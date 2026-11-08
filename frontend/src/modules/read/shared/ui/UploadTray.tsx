import { randomUUID } from "@/shared/lib";
import { useRef } from "react";
import { ImagePlus } from "lucide-react";
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

/** Choose local files → they go straight into the pool (bytes direct to
 *  Storage, see the upload features). No staging step: the pool is where images
 *  are picked and ordered. Files arrive in the order the system picker gives. */
export function UploadTray({ onConfirm, busy, uploadStatus }: UploadTrayProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  const upload = async (files: FileList | null) => {
    if (!files) return;
    const images = Array.from(files).filter((f) => f.type.startsWith("image/"));
    if (images.length === 0) return;
    await onConfirm(images.map((file) => ({ id: randomUUID(), file })));
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

      <button
        onClick={() => inputRef.current?.click()}
        disabled={busy}
        className="flex w-fit items-center gap-1.5 rounded-md border border-[var(--owl-border)] px-3 py-1.5 text-sm text-[var(--owl-brown)] hover:bg-[var(--owl-brown-mid)]/10 transition-colors cursor-pointer disabled:opacity-50"
      >
        <ImagePlus size={15} aria-hidden="true" />
        {busy ? "Uploading…" : "Choose images"}
      </button>

      {busy && <CollectProgress status={uploadStatus} />}
    </div>
  );
}
