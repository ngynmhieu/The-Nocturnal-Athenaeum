import { AnimatePresence, motion } from "motion/react";
import type { LucideIcon } from "lucide-react";
import { Link } from "react-router";
import { FADE } from "../constants";

interface NavItemProps {
  to: string;
  label: string;
  icon: LucideIcon;
  active: boolean;
  open: boolean;
}

export function NavItem({ to, label, icon: Icon, active, open }: NavItemProps) {
  return (
    <Link
      to={to}
      className={`
        flex items-center gap-3 mx-2 px-[0.65rem] py-2 rounded-lg text-sm transition-colors
        ${active
          ? "bg-[var(--owl-brown)]/15 text-[var(--owl-brown-deep)] font-medium"
          : "text-[var(--owl-brown)] hover:bg-[var(--owl-brown)]/10"
        }
      `}
    >
      <div className="flex size-5 shrink-0 items-center justify-center">
        <Icon size={18} aria-hidden="true" />
      </div>
      <AnimatePresence>
        {open && (
          <motion.span
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={FADE}
            className="flex items-center flex-1 min-w-0"
          >
            <span className="truncate whitespace-nowrap">{label}</span>
          </motion.span>
        )}
      </AnimatePresence>
    </Link>
  );
}
