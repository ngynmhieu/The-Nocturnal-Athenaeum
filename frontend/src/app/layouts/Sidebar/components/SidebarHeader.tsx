import { AnimatePresence, motion } from "motion/react";
import { PanelLeft, PanelRight } from "lucide-react";
import owlIcon from "@/shared/assets/owl_reading_book_with_glasses.png";
import { SPRING } from "../constants";

interface SidebarHeaderProps {
  open: boolean;
  toggle: () => void;
}

export function SidebarHeader({ open, toggle }: SidebarHeaderProps) {
  return (
    <div className="flex items-center gap-3 px-3 py-3 border-b border-[var(--owl-border)] shrink-0">

      {/* Owl — always a button, but non-interactive when open (PanelRight handles closing) */}
      <button
        onClick={toggle}
        aria-label="Open sidebar"
        className={`group relative shrink-0 w-8 h-8 flex items-center justify-center rounded-lg text-[var(--owl-brown)] transition-colors ${!open ? "hover:bg-[var(--owl-brown)]/10" : "pointer-events-none"}`}
      >
        <img
          src={owlIcon}
          alt=""
          className={`absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 h-12 w-12 object-contain ${!open ? "transition-opacity duration-150 group-hover:opacity-0" : ""}`}
        />
        {!open && (
          <PanelLeft
            size={18}
            className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 opacity-0 transition-opacity duration-150 group-hover:opacity-100"
          />
        )}
      </button>

      {/* PanelRight — slides from owl position to the right when sidebar opens */}
      <AnimatePresence>
        {open && (
          <motion.button
            onClick={toggle}
            aria-label="Close sidebar"
            initial={{ opacity: 0, x: -32 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -32 }}
            transition={SPRING}
            className="shrink-0 ml-auto w-8 h-8 flex items-center justify-center rounded-lg text-[var(--owl-brown)] hover:bg-[var(--owl-brown)]/10 transition-colors"
          >
            <PanelRight size={18} />
          </motion.button>
        )}
      </AnimatePresence>

    </div>
  );
}
