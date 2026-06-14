import { AnimatePresence, motion } from "motion/react";
import type { LucideIcon } from "lucide-react";
import { Link } from "react-router";
import { Tooltip } from "@/shared/ui";
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
    <Tooltip content={label} side="right" disabled={open}>
    <Link
      to={to}
      className={`
        flex gap-3 mx-2 px-[0.3rem] py-1 rounded-sm text-sm transition-colors
        ${active && open
          ? "bg-[var(--owl-brown)]/10 text-[var(--owl-brown-deep)] font-medium backdrop-blur-sm"
          : "text-[var(--owl-brown)]"
        }
        ${open ? "hover:bg-[var(--owl-brown-mid)]/15 hover:backdrop-blur-sm" : ""}
      `}
    >
      <div className="flex size-5 shrink-0 justify-center items-center">
        <Icon size={16} aria-hidden="true" />
      </div>
      <AnimatePresence>
        {open && (
          <motion.span
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={FADE}
            className="flex flex-1 min-w-0 items-center"
          >
            <span className="truncate whitespace-nowrap">{label}</span>
          </motion.span>
        )}
      </AnimatePresence>
    </Link>
    </Tooltip>
  );
}
