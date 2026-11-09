import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence } from "motion/react";
import {
  ArrowDown,
  ArrowDownToLine,
  ArrowUp,
  ArrowUpToLine,
  Languages,
  Sparkles,
  Trash2,
  Undo2,
} from "lucide-react";
import { Dropdown, DropdownItem } from "@/shared/ui";
import type { Page } from "../../../entities";

/** The dropdown's size at its tallest (Dropdown is w-48; nine items ≈ 22.5rem
 *  tall) — used to keep the menu on screen when it opens near an edge. */
const MENU_WIDTH_PX = 192;
const MENU_HEIGHT_PX = 360;
const EDGE_GAP_PX = 8;

interface PageEditOverlayProps {
  page: Page;
  /** This page's menu is the open one (only one at a time, owned by `Reader`). */
  menuOpen: boolean;
  onMenuOpenChange: (open: boolean) => void;
  /** This page is being removed or moved right now. */
  busy: boolean;
  onRemove: (page: Page) => void;
  /** Swap this page with the one above (-1) or below (1). Omitted at the
   *  matching end of the section, where there's nowhere to move. */
  onMoveUp?: (page: Page) => void;
  onMoveDown?: (page: Page) => void;
  /** Open the add flow so new pages land at `position` (the pages there move down). */
  onAddAt: (position: number) => void;
  /** Make an upscaled preview. Omitted when the page already has an upscale or
   *  is already large. */
  onUpscale?: (page: Page) => void;
  /** Delete the accepted upscale. Present only when one exists. */
  onRemoveUpscale?: (page: Page) => void;
  /** Start translate-by-reference (enters pick-reference mode). */
  onTranslate?: (page: Page) => void;
  /** Delete the accepted English translation. Present only when one exists. */
  onRemoveTranslation?: (page: Page) => void;
  /** Another upscale / translate is running or awaiting Accept / Discard: the
   *  version items show but are disabled (one at a time). */
  versionsLocked?: boolean;
  /** Pick-reference mode is on: a click picks this page instead of opening the
   *  menu. `target` is the page being translated (clicking it does nothing);
   *  `suggested` marks its neighbours, the likely reference. */
  pick?: { role: "target" | "suggested" | "other"; onPick: (page: Page) => void };
}

/** Edit-mode layer over one page: click (or right-click) anywhere on it and a
 *  menu opens right there — move it up / down one place, add pages in front of /
 *  behind it, upscale it, translate it by reference, remove an accepted version,
 *  or remove the page (asks twice, since removing deletes the image for good).
 *
 *  The menu is portalled to <body> with fixed positioning: the page box has
 *  `content-visibility: auto`, whose paint containment would clip a menu
 *  rendered inside it (a short strip page can be shorter than the menu). */
export function PageEditOverlay({
  page,
  menuOpen,
  onMenuOpenChange,
  busy,
  onRemove,
  onMoveUp,
  onMoveDown,
  onAddAt,
  onUpscale,
  onRemoveUpscale,
  onTranslate,
  onRemoveTranslation,
  versionsLocked = false,
  pick,
}: PageEditOverlayProps) {
  const [menuArmed, setMenuArmed] = useState(false);
  // Where the menu opens, in viewport coordinates.
  const [menuAt, setMenuAt] = useState({ left: 0, top: 0 });
  const label = `page ${page.position + 1}`;

  const closeMenu = () => {
    setMenuArmed(false);
    onMenuOpenChange(false);
  };

  const showMenuAt = (event: React.MouseEvent<HTMLButtonElement>) => {
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

  // Left click toggles the menu; right click always (re)opens it at the pointer.
  // In pick-reference mode both pick this page instead (the target ignores it).
  const onClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    if (pick) {
      if (pick.role !== "target") pick.onPick(page);
      return;
    }
    if (menuOpen) closeMenu();
    else showMenuAt(event);
  };
  const onContextMenu = (event: React.MouseEvent<HTMLButtonElement>) => {
    event.preventDefault();
    if (pick) {
      if (pick.role !== "target") pick.onPick(page);
      return;
    }
    showMenuAt(event);
  };

  /** A menu item that closes the menu, then runs `action` on this page. */
  const act = (action: (page: Page) => void) => () => {
    closeMenu();
    action(page);
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
        aria-label={pick ? (pick.role === "target" ? `Translating ${label}` : `Use ${label} as the reference`) : `Edit ${label}`}
        onClick={onClick}
        onContextMenu={onContextMenu}
        className={`absolute inset-0 transition-colors ${pick?.role === "target" ? "cursor-default" : "cursor-pointer"} ${
          menuOpen ? "bg-[var(--owl-brown-deep)]/15" : "hover:bg-[var(--owl-brown-deep)]/5"
        } ${busy ? "animate-pulse bg-[var(--owl-brown-deep)]/25" : ""}`}
      />

      {/* Pick-reference mode: outline the target, dash its likely references. */}
      {pick?.role === "target" && (
        <div className="pointer-events-none absolute inset-0 border-4 border-[var(--owl-orange)]" />
      )}
      {pick?.role === "suggested" && (
        <div className="pointer-events-none absolute inset-0 border-4 border-dashed border-[var(--owl-orange)]/70" />
      )}

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
              {onMoveUp && (
                <DropdownItem
                  icon={<ArrowUp size={14} aria-hidden="true" />}
                  onClick={() => {
                    closeMenu();
                    onMoveUp(page);
                  }}
                >
                  Move up one page
                </DropdownItem>
              )}
              {onMoveDown && (
                <DropdownItem
                  icon={<ArrowDown size={14} aria-hidden="true" />}
                  onClick={() => {
                    closeMenu();
                    onMoveDown(page);
                  }}
                >
                  Move down one page
                </DropdownItem>
              )}
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
              {onUpscale && (
                <DropdownItem
                  icon={<Sparkles size={14} aria-hidden="true" />}
                  disabled={versionsLocked}
                  onClick={act(onUpscale)}
                >
                  Upscale
                </DropdownItem>
              )}
              {onRemoveUpscale && (
                <DropdownItem
                  icon={<Undo2 size={14} aria-hidden="true" />}
                  disabled={versionsLocked}
                  onClick={act(onRemoveUpscale)}
                >
                  Remove upscale
                </DropdownItem>
              )}
              {onTranslate && (
                <DropdownItem
                  icon={<Languages size={14} aria-hidden="true" />}
                  disabled={versionsLocked}
                  onClick={act(onTranslate)}
                >
                  Translate by reference…
                </DropdownItem>
              )}
              {onTranslate && (
                <DropdownItem icon={<Languages size={14} aria-hidden="true" />} disabled>
                  Translate directly — coming later
                </DropdownItem>
              )}
              {onRemoveTranslation && (
                <DropdownItem
                  icon={<Undo2 size={14} aria-hidden="true" />}
                  disabled={versionsLocked}
                  onClick={act(onRemoveTranslation)}
                >
                  Remove translation
                </DropdownItem>
              )}
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
