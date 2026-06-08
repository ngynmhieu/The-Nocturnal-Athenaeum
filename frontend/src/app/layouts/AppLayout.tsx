import { Outlet } from "react-router";
import { GradientBackground } from "@/shared/ui";
import { Header } from "./Header";

export function AppLayout() {
  return (
    <GradientBackground>
      <div className="flex flex-col h-screen">
        <Header />
        <main className="flex-1 relative overflow-hidden">
          <Outlet />
        </main>
      </div>
    </GradientBackground>
  );
}
