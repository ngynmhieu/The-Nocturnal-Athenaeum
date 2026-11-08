import type { ImportStatus } from "../importStatus";

/** "Collecting 12 / 40 into the pool…" — from the per-item statuses a collect reports. */
export function CollectProgress({ status = {} }: { status?: Record<string, ImportStatus> }) {
  const values = Object.values(status);
  if (values.length === 0) return null;
  const finished = values.filter((value) => value !== "importing").length;
  const failed = values.filter((value) => value === "error").length;
  return (
    <p className="text-sm text-[var(--owl-brown-muted)]">
      Collecting {finished} / {values.length} into the pool…
      {failed > 0 && ` (${failed} failed)`}
    </p>
  );
}
