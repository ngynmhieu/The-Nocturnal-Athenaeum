import { useState } from "react";
import { AnimatePresence } from "motion/react";
import { ArrowDownToLine, ArrowUpToLine, Trash2, X } from "lucide-react";
import { Dropdown, DropdownItem } from "@/shared/ui";
import type { Page } from "../../../entities";

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

/** Edit-mode layer over one page: an ✕ in the corner (click once to arm, again
 *  to remove) and, on clicking the page itself, a menu — remove it, or add pages
 *  in front of / behind it. Removing deletes the image for good, so both paths
 *  ask twice. */
export function PageEditOverlay({
  page,
  menuOpen,
  onMenuOpenChange,
  removing,
  onRemove,
  onAddAt,
}: PageEditOverlayProps) {
  const [armed, setArmed] = useState(false);
  const [menuArmed, setMenuArmed] = useState(false);
  const label = `page ${page.position + 1}`;

  const closeMenu = () => {
    setMenuArmed(false);
    onMenuOpenChange(false);
  };

  return (
    // `data-page-edit` lets `Reader` tell a click inside this page's menu from a
    // click elsewhere (which closes it).
    <div className="absolute inset-0" data-page-edit={page.id}>
      {/* The whole page is the click target for the menu. */}
      <button
        type="button"
        aria-label={`Edit ${label}`}
        onClick={() => onMenuOpenChange(!menuOpen)}
        className={`absolute inset-0 cursor-pointer transition-colors ${
          menuOpen ? "bg-[var(--owl-brown-deep)]/15" : "hover:bg-[var(--owl-brown-deep)]/5"
        } ${removing ? "animate-pulse bg-[var(--owl-brown-deep)]/25" : ""}`}
      />

      <span className="pointer-events-none absolute left-2 top-2 rounded-md bg-[var(--background)]/85 px-2 py-0.5 text-xs text-[var(--owl-brown-deep)]">
        {page.position + 1}
      </span>

      <button
        type="button"
        aria-label={armed ? `Confirm removing ${label}` : `Remove ${label}`}
        disabled={removing}
        onClick={() => {
          if (armed) {
            setArmed(false);
            onRemove(page);
          } else {
            setArmed(true);
          }
        }}
        onMouseLeave={() => setArmed(false)}
        onBlur={() => setArmed(false)}
        className={`absolute right-2 top-2 flex items-center gap-1 rounded-full border border-[var(--owl-border)] shadow-sm transition-colors cursor-pointer disabled:cursor-wait ${
          armed
            ? "bg-[var(--owl-brown-deep)] px-3 py-1 text-xs text-[var(--background)]"
            : "bg-[var(--background)]/90 p-1.5 text-[var(--owl-brown)] hover:text-[var(--owl-brown-deep)]"
        }`}
      >
        <X size={armed ? 13 : 16} aria-hidden="true" />
        {armed && "Remove?"}
      </button>

      <AnimatePresence>
        {menuOpen && (
            <Dropdown position="left-1/2 top-1/3 -translate-x-1/2">
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
        )}
      </AnimatePresence>
    </div>
  );
}
