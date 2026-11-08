import { useState } from "react";

/** How much of the reading area the page strip fills, on wide screens. */
export type ReaderWidth = "full" | "three-quarters" | "half";

export const READER_WIDTHS: { value: ReaderWidth; label: string }[] = [
  { value: "full", label: "Full" },
  { value: "three-quarters", label: "¾" },
  { value: "half", label: "½" },
];

const STORAGE_KEY = "lector.readerWidth";
const DEFAULT_WIDTH: ReaderWidth = "full";

function isReaderWidth(value: unknown): value is ReaderWidth {
  return READER_WIDTHS.some((w) => w.value === value);
}

// Storage access can throw (private windows, blocked site data) — fall back to
// the default rather than breaking the reader.
function readStored(): ReaderWidth {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return isReaderWidth(stored) ? stored : DEFAULT_WIDTH;
  } catch {
    return DEFAULT_WIDTH;
  }
}

/** The reader's page-strip width, remembered in this browser (localStorage) —
 *  one preference for every manga, defaulting to full width. */
export function useReaderWidth() {
  const [width, setWidthState] = useState<ReaderWidth>(readStored);

  const setWidth = (next: ReaderWidth) => {
    setWidthState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Not persisted this time; the choice still applies for this visit.
    }
  };

  return { width, setWidth };
}
