import { AnimatePresence, motion } from "motion/react";
import { useSidebar } from "./useSidebar";
import { WIDTH_EXPANDED, WIDTH_COLLAPSED, SPRING } from "./constants";
import { SidebarHeader } from "./components/SidebarHeader";
import { SidebarContent } from "./components/SidebarContent";
import { SidebarFooter } from "./components/SidebarFooter";

export function Sidebar() {
  const { open, toggle, close, isMobile } = useSidebar();

  const body = (
    <>
      <SidebarHeader open={open} toggle={toggle} />
      <SidebarContent open={open} />
      <SidebarFooter open={open} />
    </>
  );

  // Phone: a drawer over the page (opened from the header's menu button), so the
  // content keeps the full screen width.
  if (isMobile) {
    return (
      <AnimatePresence>
        {open && (
          <>
            <motion.div
              key="backdrop"
              className="fixed inset-0 z-40 bg-[var(--owl-brown-deep)]/25"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={close}
              aria-hidden="true"
            />
            <motion.aside
              key="drawer"
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={SPRING}
              style={{ width: WIDTH_EXPANDED }}
              className="fixed inset-y-0 left-0 z-50 flex max-w-[85vw] flex-col border-r border-[var(--owl-border)] bg-[var(--owl-parchment)] shadow-lg"
            >
              {body}
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    );
  }

  return (
    <motion.aside
      animate={{ width: open ? WIDTH_EXPANDED : WIDTH_COLLAPSED }}
      transition={SPRING}
      className="relative flex flex-col h-full border-r border-[var(--owl-border)] overflow-hidden shrink-0 z-10"
    >
      {body}
    </motion.aside>
  );
}
