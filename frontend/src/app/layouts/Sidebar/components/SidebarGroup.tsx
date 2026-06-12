import { AnimatePresence, motion } from "motion/react";
import type { ReactNode } from "react";
import { FADE } from "../constants";

interface SidebarGroupProps {
  label: string;
  open: boolean;
  children: ReactNode;
}

export function SidebarGroup({ label, open, children }: SidebarGroupProps) {
  return (
    <div className="px-2 pb-2">
      <AnimatePresence>
        {open && (
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={FADE}
            className="px-2 pb-1 text-xs font-medium text-[var(--owl-brown-muted)] uppercase tracking-wider whitespace-nowrap"
          >
            {label}
          </motion.p>
        )}
      </AnimatePresence>
      {children}
    </div>
  );
}
