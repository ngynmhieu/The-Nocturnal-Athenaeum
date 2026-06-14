import { motion } from "motion/react";

interface DropdownProps {
  position?: string;
  children: React.ReactNode;
}

const anim = {
  initial: { opacity: 0, scale: 0.95 },
  animate: { opacity: 1, scale: 1 },
  exit: { opacity: 0, scale: 0.95 },
  transition: { duration: 0.12 },
};

export function Dropdown({ position, children }: DropdownProps) {
  return (
    <motion.div {...anim} className={`${position ? `absolute ${position}` : ""} w-48 rounded-lg border border-[var(--owl-brown)]/20 bg-[var(--background)] shadow-md py-1 z-50`}>
      {children}
    </motion.div>
  );
}

interface DropdownSectionProps {
  children: React.ReactNode;
}

export function DropdownSection({ children }: DropdownSectionProps) {
  return (
    <div className="px-3 py-2 border-b border-[var(--owl-brown)]/10">
      {children}
    </div>
  );
}

interface DropdownItemProps {
  icon?: React.ReactNode;
  onClick?: () => void;
  children: React.ReactNode;
}

export function DropdownItem({ icon, onClick, children }: DropdownItemProps) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-2 w-full px-3 py-2 text-xs cursor-pointer text-[var(--owl-brown)] hover:bg-[var(--owl-brown)]/10 hover:text-[var(--owl-brown-deep)] backdrop-blur-sm transition-colors"
    >
      {icon}
      {children}
    </button>
  );
}
