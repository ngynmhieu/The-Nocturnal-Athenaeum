import { X } from "lucide-react";

interface PickReferenceBannerProps {
  /** The page being translated (shown 1-based). */
  targetPosition: number;
  onCancel: () => void;
}

/** Sticky strip over the reader while choosing a translate-by-reference source. */
export function PickReferenceBanner({ targetPosition, onCancel }: PickReferenceBannerProps) {
  return (
    <div
      role="status"
      className="sticky top-0 z-30 flex items-center justify-center gap-3 border-b border-[var(--owl-border)] bg-[var(--owl-cream)]/95 px-4 py-2 text-sm text-[var(--owl-brown-deep)] shadow-sm backdrop-blur-sm"
    >
      <span>Pick the reference page for p.{targetPosition + 1} · Esc to cancel</span>
      <button
        type="button"
        onClick={onCancel}
        aria-label="Cancel picking a reference page"
        className="rounded-md p-1 text-[var(--owl-brown-muted)] transition-colors hover:bg-[var(--owl-brown-mid)]/10 hover:text-[var(--owl-brown-deep)] cursor-pointer"
      >
        <X size={16} aria-hidden="true" />
      </button>
    </div>
  );
}
