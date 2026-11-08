import { useEffect, useRef, useState } from "react";
import type { Page } from "../../entities";
import { PageView } from "./components/PageView";
import { PageEditOverlay } from "./components/PageEditOverlay";

/** Ignore scroll jitter smaller than this (px) when deciding direction. */
const SCROLL_DIRECTION_THRESHOLD = 8;
/** Within this distance (px) of the top, the header always shows. */
const TOP_ZONE = 64;
/** How long (ms) to ignore scrolling after the header toggles — its fold
 *  animation resizes this box, and near the bottom the browser nudges
 *  scrollTop to fit, which would otherwise read as a scroll and flip it back. */
const SETTLE_MS = 350;

interface ReaderProps {
  pages: Page[];
  /** path → signed URL map (batch-signed once per section by the page). */
  urls: Record<string, string>;
  /** Fires when the page header should hide (scrolling down) or show again
   *  (scrolling up, or back near the top) — so it stays out of the way while reading. */
  onHeaderHiddenChange?: (hidden: boolean) => void;
  /** Edit mode: each page gets remove / add-before / add-after controls. */
  editing?: boolean;
  /** The page currently being removed, if any. */
  removingId?: string | null;
  onRemovePage?: (page: Page) => void;
  /** Add pages so they land at this position (pages from there move down). */
  onAddPagesAt?: (position: number) => void;
}

/** The reading view: a vertical long-strip of pages loading straight from the
 *  Storage CDN. Off-screen pages skip layout/paint via content-visibility and
 *  load lazily, so large volumes stay smooth. */
export function Reader({
  pages,
  urls,
  onHeaderHiddenChange,
  editing = false,
  removingId = null,
  onRemovePage,
  onAddPagesAt,
}: ReaderProps) {
  // One page menu at a time; a click anywhere outside it closes it.
  const [menuPageId, setMenuPageId] = useState<string | null>(null);
  const openMenuId = editing ? menuPageId : null;
  useEffect(() => {
    if (!openMenuId) return;
    const onPointerDown = (event: PointerEvent) => {
      const owner = (event.target as Element | null)?.closest?.("[data-page-edit]");
      if (owner?.getAttribute("data-page-edit") !== openMenuId) setMenuPageId(null);
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [openMenuId]);

  const lastTop = useRef(0);
  const hidden = useRef(false);
  const settleUntil = useRef(0);

  const onScroll = (event: React.UIEvent<HTMLDivElement>) => {
    const top = event.currentTarget.scrollTop;
    if (event.timeStamp < settleUntil.current) {
      lastTop.current = top;
      return;
    }
    const delta = top - lastTop.current;
    if (Math.abs(delta) < SCROLL_DIRECTION_THRESHOLD) return;
    lastTop.current = top;
    const nextHidden = top > TOP_ZONE && delta > 0;
    if (nextHidden !== hidden.current) {
      hidden.current = nextHidden;
      settleUntil.current = event.timeStamp + SETTLE_MS;
      onHeaderHiddenChange?.(nextHidden);
    }
  };

  return (
    <div className="h-full overflow-y-auto" onScroll={onScroll}>
      <div className="flex w-full flex-col">
        {pages.map((page) => (
          <PageView key={page.id} page={page} imageUrl={urls[page.storagePath]}>
            {editing && onRemovePage && onAddPagesAt && (
              <PageEditOverlay
                page={page}
                menuOpen={openMenuId === page.id}
                onMenuOpenChange={(open) => setMenuPageId(open ? page.id : null)}
                removing={removingId === page.id}
                onRemove={onRemovePage}
                onAddAt={onAddPagesAt}
              />
            )}
          </PageView>
        ))}
      </div>
    </div>
  );
}
