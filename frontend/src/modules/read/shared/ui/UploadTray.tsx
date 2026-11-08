import { randomUUID } from "@/shared/lib";
import { useEffect, useRef, useState } from "react";
import { ImagePlus } from "lucide-react";
import { useClickSelect } from "../useClickSelect";
import type { ImportStatus } from "../importStatus";
import { PickerGrid } from "./PickerGrid";

interface StagedFile {
  id: string;
  file: File;
  previewUrl: string;
}

interface UploadTrayProps {
  /** Called with `{id, file}` pairs in pick order — the id lets the caller
   *  report per-file `uploadStatus` back via the same key. */
  onConfirm: (items: { id: string; file: File }[]) => Promise<void> | void;
  busy: boolean;
  /** Per-file status while `busy`, keyed by the id passed to `onConfirm`. */
  uploadStatus?: Record<string, ImportStatus>;
  confirmLabel?: string;
}

/** Choose local files → pick + order (click, same as ScrapePicker) → upload.
 *  Bytes later go straight to Storage (see upload features). */
export function UploadTray({ onConfirm, busy, uploadStatus, confirmLabel = "Upload" }: UploadTrayProps) {
  const [staged, setStaged] = useState<StagedFile[]>([]);
  const { picked, setPicked, onItemClick } = useClickSelect(staged.map((item) => item.id));
  const inputRef = useRef<HTMLInputElement>(null);
  const stagedRef = useRef<StagedFile[]>([]);

  // Track the latest staged set so unmount can revoke exactly the URLs still live.
  useEffect(() => {
    stagedRef.current = staged;
  }, [staged]);

  // Revoke every remaining preview URL when the tray unmounts.
  useEffect(() => {
    return () => stagedRef.current.forEach((item) => URL.revokeObjectURL(item.previewUrl));
  }, []);

  const addFiles = (files: FileList | null) => {
    if (!files) return;
    const images = Array.from(files).filter((f) => f.type.startsWith("image/"));
    setStaged((prev) => [
      ...prev,
      ...images.map((file) => ({
        id: randomUUID(),
        file,
        previewUrl: URL.createObjectURL(file),
      })),
    ]);
  };

  const confirm = async () => {
    if (picked.length === 0) return;
    const byId = new Map(staged.map((item) => [item.id, item]));
    await onConfirm(picked.map((id) => ({ id, file: byId.get(id)!.file })));
    staged.forEach((item) => URL.revokeObjectURL(item.previewUrl));
    setStaged([]);
    setPicked([]);
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
          addFiles(e.target.files);
          e.target.value = ""; // allow re-picking the same files
        }}
      />

      <button
        onClick={() => inputRef.current?.click()}
        disabled={busy}
        className="flex w-fit items-center gap-1.5 rounded-md border border-[var(--owl-border)] px-3 py-1.5 text-sm text-[var(--owl-brown)] hover:bg-[var(--owl-brown-mid)]/10 transition-colors cursor-pointer disabled:opacity-50"
      >
        <ImagePlus size={15} aria-hidden="true" />
        Choose images
      </button>

      <PickerGrid
        items={staged.map((item) => ({ key: item.id, previewUrl: item.previewUrl, label: item.file.name }))}
        picked={picked}
        onItemClick={onItemClick}
        onSelectAll={() => setPicked(staged.map((item) => item.id))}
        onClear={() => setPicked([])}
        busy={busy}
        busyLabel="Uploading…"
        confirmLabel={confirmLabel}
        importStatus={uploadStatus}
        onConfirm={confirm}
      />
    </div>
  );
}
