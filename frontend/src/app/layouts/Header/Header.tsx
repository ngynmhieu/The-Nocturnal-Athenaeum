import { Menu } from "lucide-react";
import { useSidebar } from "../Sidebar";

export function Header() {
  const { isMobile, toggle } = useSidebar();

  return (
    <header className="relative z-20 flex items-center gap-2 px-4 md:px-6 h-14">
      {/* Phone only: the sidebar is a hidden drawer, so the header opens it. */}
      {isMobile && (
        <button
          onClick={toggle}
          aria-label="Open menu"
          className="-ml-1 p-1.5 rounded-lg text-[var(--owl-brown)] hover:bg-[var(--owl-brown)]/10 transition-colors cursor-pointer"
        >
          <Menu size={20} />
        </button>
      )}
      <span className="text-sm font-semibold tracking-wide text-[var(--owl-brown-deep)]">
        THE NOCTURNAL ATHENAEUM
      </span>
    </header>
  );
}
