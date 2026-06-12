import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { SidebarContext } from "./useSidebar";

export function SidebarProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);

  const toggle = useCallback(() => setOpen((v) => !v), []);

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
    <SidebarContext.Provider value={{ open, toggle }}>
      {children}
    </SidebarContext.Provider>
  );
}
