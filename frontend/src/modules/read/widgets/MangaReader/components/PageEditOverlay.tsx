import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence } from "motion/react";
import { ArrowDownToLine, ArrowUpToLine, Trash2 } from "lucide-react";
import { Dropdown, DropdownItem } from "@/shared/ui";
import type { Page } from "../../../entities";

/** The dropdown's size (Dropdown is w-48; three items ≈ 7.5rem tall) — used to
 *  keep the menu on screen when it opens near an edge. */
const MENU_WIDTH_PX = 192;
const MENU_HEIGHT_PX = 124;
const EDGE_GAP_PX = 8;

interface PageEditOverlayProps {
  page: Page;
  /** This page's menu is the open one (only one at a time, owned by `Reader`). */
  menuOpen: boolean;
  onMenuOpenChange: (open: boolean) => void;
  /** This page is being removed right now. */
  removing: boolean;
  onRemove: (page: Page) => void;
  /** Open the add flow so new pages land at `position` (the pages there move down). */
  onAddAt: (position: number) => void;
}

/** Edit-mode layer over one page: click anywhere on it and a menu opens right
 *  there — add pages in front of / behind it, or remove it (asks twice, since
 *  removing deletes the image for good).
 *
 *  The menu is portalled to <body> with fixed positioning: the page box has
 *  `content-visibility: auto`, whose paint containment would clip a menu
 *  rendered inside it (a short strip page can be shorter than the menu). */
export function PageEditOverlay({
  page,
  menuOpen,
  onMenuOpenChange,
  removing,
  onRemove,
  onAddAt,
}: PageEditOverlayProps) {
  const [menuArmed, setMenuArmed] = useState(false);
  // Where the menu opens, in viewport coordinates.
  const [menuAt, setMenuAt] = useState({ left: 0, top: 0 });
  const label = `page ${page.position + 1}`;

  const closeMenu = () => {
    setMenuArmed(false);
    onMenuOpenChange(false);
  };

  const openAt = (event: React.MouseEvent<HTMLButtonElement>) => {
    if (menuOpen) {
      closeMenu();
      return;
    }
    const { clientX: x, clientY: y } = event;
    setMenuAt({
      // Shift left / open upward when the click is too close to the screen's
      // right or bottom edge.
      left: Math.max(EDGE_GAP_PX, Math.min(x, window.innerWidth - MENU_WIDTH_PX - EDGE_GAP_PX)),
      top: y + MENU_HEIGHT_PX + EDGE_GAP_PX > window.innerHeight ? Math.max(EDGE_GAP_PX, y - MENU_HEIGHT_PX) : y,
    });
    setMenuArmed(false);
    onMenuOpenChange(true);
  };

  // A fixed menu doesn't move with the page, so scrolling closes it.
  useEffect(() => {
    if (!menuOpen) return;
    const close = () => onMenuOpenChange(false);
    window.addEventListener("scroll", close, { capture: true, passive: true });
    return () => window.removeEventListener("scroll", close, { capture: true });
  }, [menuOpen, onMenuOpenChange]);

  return (
    // `data-page-edit` lets `Reader` tell a click inside this page's menu from a
    // click elsewhere (which closes it).
    <div className="absolute inset-0" data-page-edit={page.id}>
      {/* The whole page is the click target for the menu. */}
      <button
        type="button"
        aria-label={`Edit ${label}`}
        onClick={openAt}
        className={`absolute inset-0 cursor-pointer transition-colors ${
          menuOpen ? "bg-[var(--owl-brown-deep)]/15" : "hover:bg-[var(--owl-brown-deep)]/5"
        } ${removing ? "animate-pulse bg-[var(--owl-brown-deep)]/25" : ""}`}
      />

      <span className="pointer-events-none absolute left-2 top-2 rounded-md bg-[var(--background)]/85 px-2 py-0.5 text-xs text-[var(--owl-brown-deep)]">
        {page.position + 1}
      </span>

      {createPortal(
      <AnimatePresence>
        {menuOpen && (
          // Same `data-page-edit` as the page, so Reader still treats clicks in
          // the (portalled) menu as inside this page.
          <div data-page-edit={page.id} className="fixed z-50" style={{ left: menuAt.left, top: menuAt.top }}>
            <Dropdown>
              <DropdownItem
                icon={<ArrowUpToLine size={14} aria-hidden="true" />}
                onClick={() => {
                  closeMenu();
                  onAddAt(page.position);
                }}
              >
                Add page before
              </DropdownItem>
              <DropdownItem
                icon={<ArrowDownToLine size={14} aria-hidden="true" />}
                onClick={() => {
                  closeMenu();
                  onAddAt(page.position + 1);
                }}
              >
                Add page after
              </DropdownItem>
              <DropdownItem
                icon={<Trash2 size={14} aria-hidden="true" />}
                onClick={() => {
                  if (!menuArmed) {
                    setMenuArmed(true);
                    return;
                  }
                  closeMenu();
                  onRemove(page);
                }}
              >
                {menuArmed ? "Click again to remove" : "Remove this page"}
              </DropdownItem>
            </Dropdown>
          </div>
        )}
      </AnimatePresence>,
      document.body
      )}
    </div>
  );
}
