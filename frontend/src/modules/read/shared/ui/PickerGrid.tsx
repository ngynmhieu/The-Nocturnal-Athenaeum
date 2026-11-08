import { useState } from "react";
import { Loader2 } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import type { ImportStatus } from "../importStatus";
import { PickerCard } from "./PickerCard";

export interface PickerItem {
  key: string;
  previewUrl: string;
  label?: string;
}

interface PickerGridProps {
  items: PickerItem[];
  /** Keys in pick order. */
  picked: string[];
  /** Click on item `index` (key `key`) — shift-extends from the last clicked
   *  item when `event.shiftKey`, otherwise toggles just this one. */
  onItemClick: (key: string, index: number, event: React.MouseEvent) => void;
  onSelectAll: () => void;
  onClear: () => void;
  /** Hides "Select all" — for callers that only ever want one pick (e.g. choosing a cover). */
  singleSelect?: boolean;
  busy: boolean;
  /** Shown on the confirm button while `busy` (e.g. "Importing…", "Uploading…"). */
  busyLabel: string;
  confirmLabel: string;
  /** Per-key status while `busy` — each card shows its own spinner/done state.
   *  A "done" item fades out of the grid immediately (it's landed wherever it
   *  was going — e.g. the pool grid — rather than waiting for the whole batch). */
  importStatus?: Record<string, ImportStatus>;
  itemNoun?: string;
  /** Caption after the count — defaults to the click-to-pick instruction. */
  hint?: string;
  onConfirm: () => void;
  /** Shows a "Delete N" button beside the confirm button that deletes the picked
   *  items (e.g. discarding from the pool) — first click arms it, second
   *  deletes. Omit and the grid offers no deleting. */
  onDeletePicked?: () => void;
  /** A delete is in progress. */
  deleting?: boolean;
}

/** Shared "click to pick, in order, then confirm" grid — scraped candidates and
 *  locally staged files are both just a list of `{ key, previewUrl }`, picked in
 *  click order, with the same per-card importing/done status effect. */
export function PickerGrid({
  items,
  picked,
  onItemClick,
  onSelectAll,
  onClear,
  singleSelect = false,
  busy,
  busyLabel,
  confirmLabel,
  importStatus,
  itemNoun = "image",
  hint = "click to pick, in reading order.",
  onConfirm,
  onDeletePicked,
  deleting = false,
}: PickerGridProps) {
  const [deleteArmed, setDeleteArmed] = useState(false);
  const count = `${picked.length} ${itemNoun}${picked.length > 1 ? "s" : ""}`;
  const visibleItems = items.filter((item) => importStatus?.[item.key] !== "done");
  if (visibleItems.length === 0) return null;

  return (
    <>
      <div className="flex items-center gap-3">
        <p className="text-xs text-[var(--owl-brown-muted)]">
          {visibleItems.length} {itemNoun}
          {visibleItems.length > 1 ? "s" : ""} — {hint}
        </p>
        {!singleSelect && (
          <button onClick={onSelectAll} className="text-xs text-[var(--owl-orange-deep)] hover:underline cursor-pointer">
            Select all
          </button>
        )}
        {picked.length > 0 && (
          <button onClick={onClear} className="text-xs text-[var(--owl-brown-muted)] hover:underline cursor-pointer">
            Clear
          </button>
        )}
      </div>
      <div className="grid grid-cols-[repeat(auto-fill,minmax(6rem,1fr))] gap-2 max-h-[24rem] overflow-y-auto pr-1 py-2">
        <AnimatePresence>
          {visibleItems.map((item, index) => (
            <motion.div
              key={item.key}
              layout
              initial={false}
              exit={{ opacity: 0, scale: 0.85 }}
              transition={{ duration: 0.2 }}
            >
              <PickerCard
                previewUrl={item.previewUrl}
                label={item.label}
                order={picked.includes(item.key) ? picked.indexOf(item.key) : null}
                status={importStatus?.[item.key]}
                onToggle={(event) => onItemClick(item.key, index, event)}
              />
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
      {picked.length > 0 && (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <button
            onClick={onConfirm}
            disabled={busy || deleting}
            className="flex w-fit items-center gap-1.5 rounded-md bg-[var(--owl-brown)] px-3 py-1.5 text-sm text-[var(--owl-cream)] hover:bg-[var(--owl-brown-deep)] transition-colors cursor-pointer disabled:opacity-50"
          >
            {busy && <Loader2 size={14} aria-hidden="true" className="animate-spin" />}
            {busy ? busyLabel : `${confirmLabel} ${count}`}
          </button>
          {onDeletePicked && (
            <button
              onClick={() => {
                if (!deleteArmed) {
                  setDeleteArmed(true);
                  return;
                }
                setDeleteArmed(false);
                onDeletePicked();
              }}
              onMouseLeave={() => setDeleteArmed(false)}
              onBlur={() => setDeleteArmed(false)}
              disabled={busy || deleting}
              className={`flex w-fit items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm transition-colors cursor-pointer disabled:opacity-50 ${
                deleteArmed
                  ? "border-[var(--owl-danger)] bg-[var(--owl-danger)] text-[var(--owl-cream)]"
                  : "border-[var(--owl-border)] text-[var(--owl-brown)] hover:bg-[var(--owl-brown-mid)]/10"
              }`}
            >
              {deleting && <Loader2 size={14} aria-hidden="true" className="animate-spin" />}
              {deleting ? "Deleting…" : deleteArmed ? `Confirm delete ${count}?` : `Delete ${count}`}
            </button>
          )}
        </div>
      )}
    </>
  );
}
