import { Outlet } from "react-router";
import { GradientBackground } from "@/shared/ui";
import { Header } from "./Header";
import { Sidebar, SidebarProvider } from "./Sidebar";

export function AppLayout() {
  return (
    <GradientBackground>
      <SidebarProvider>
        {/* Desktop: a fixed screen-height frame; each page scrolls inside it.
            Phone: the page itself scrolls (the document, not an inner box) —
            Safari only collapses / brings back its toolbars on a document
            scroll, so inner scroll boxes would pin them in place. */}
        <div className="flex min-h-dvh md:h-screen">
          <Sidebar />
          <div className="flex flex-col flex-1 min-w-0 md:overflow-hidden">
            <Header />
            <main className="flex-1 relative md:overflow-hidden">
              <Outlet />
            </main>
          </div>
        </div>
      </SidebarProvider>
    </GradientBackground>
  );
}
