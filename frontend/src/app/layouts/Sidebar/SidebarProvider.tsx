import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useLocation } from "react-router";
import { MOBILE_QUERY, useIsMobile } from "@/shared/lib";
import { SidebarContext } from "./useSidebar";

export function SidebarProvider({ children }: { children: ReactNode }) {
  const isMobile = useIsMobile();
  // On a phone the sidebar is a drawer over the page, so it starts closed.
  const [open, setOpen] = useState(() => !window.matchMedia(MOBILE_QUERY).matches);
  const location = useLocation();

  const toggle = useCallback(() => setOpen((v) => !v), []);
  const close = useCallback(() => setOpen(false), []);

  // Crossing into phone size closes it; on a phone, picking a page closes it too.
  // Keyed on the values that should trigger a close — not a sync of `open` itself.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (isMobile) setOpen(false);
  }, [isMobile, location.pathname]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "b" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        toggle();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [toggle]);

  return (
    <SidebarContext.Provider value={{ open, toggle, close, isMobile }}>
      {children}
    </SidebarContext.Provider>
  );
}
