import { Outlet } from "react-router";
import { GradientBackground } from "@/shared/ui";
import { Header } from "./Header";
import { Sidebar, SidebarProvider } from "./Sidebar";

export function AppLayout() {
  return (
    <GradientBackground>
      <SidebarProvider>
        <div className="flex h-screen">
          <Sidebar />
          <div className="flex flex-col flex-1 overflow-hidden">
            <Header />
            <main className="flex-1 relative overflow-hidden">
              <Outlet />
            </main>
          </div>
        </div>
      </SidebarProvider>
    </GradientBackground>
  );
}
