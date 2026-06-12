import { AnimatePresence, motion } from "motion/react";
import { User } from "lucide-react";
import { FADE } from "../constants";

interface SidebarFooterProps {
  open: boolean;
}

export function SidebarFooter({ open }: SidebarFooterProps) {
  return (
    <div className={`border-t border-[var(--owl-border)] p-2 shrink-0 flex items-center ${open ? "justify-start" : "justify-center"}`}>
      <div className="flex items-center gap-3 px-2 py-2 rounded-lg">
        <div className="shrink-0 w-8 h-8 rounded-full bg-[var(--owl-brown)]/20 flex items-center justify-center">
          <User size={16} className="text-[var(--owl-brown)]" />
        </div>
        <AnimatePresence>
          {open && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={FADE}
              className="overflow-hidden min-w-0"
            >
              <p className="text-xs font-medium text-[var(--owl-brown-deep)] whitespace-nowrap truncate">
                Guest User
              </p>
              <p className="text-xs text-[var(--owl-brown-muted)] whitespace-nowrap truncate">
                guest@nocturnal.app
              </p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
