import { createContext, useContext } from "react";

export type SidebarContextValue = {
  open: boolean;
  toggle: () => void;
  close: () => void;
  /** Phone-sized viewport: the sidebar is a drawer over the content, not a column. */
  isMobile: boolean;
};

export const SidebarContext = createContext<SidebarContextValue | null>(null);

export function useSidebar() {
  const ctx = useContext(SidebarContext);
  if (!ctx) throw new Error("useSidebar must be used within SidebarProvider");
  return ctx;
}
