import { motion } from "motion/react";
import { useSidebar } from "./useSidebar";
import { WIDTH_EXPANDED, WIDTH_COLLAPSED, SPRING } from "./constants";
import { SidebarHeader } from "./components/SidebarHeader";
import { SidebarContent } from "./components/SidebarContent";
import { SidebarFooter } from "./components/SidebarFooter";

export function Sidebar() {
  const { open, toggle } = useSidebar();

  return (
    <motion.aside
      animate={{ width: open ? WIDTH_EXPANDED : WIDTH_COLLAPSED }}
      transition={SPRING}
      className="relative flex flex-col h-full border-r border-[var(--owl-border)] overflow-hidden shrink-0 z-10"
    >
      <SidebarHeader open={open} toggle={toggle} />
      <SidebarContent open={open} />
      <SidebarFooter open={open} />
    </motion.aside>
  );
}
