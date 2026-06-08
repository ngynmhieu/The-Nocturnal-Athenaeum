import { Link } from "react-router";
import owlIcon from "@/shared/assets/owl_reading_book_with_glasses.png";

export function Header() {
  return (
    <header className="relative z-20 gap-4 flex items-center px-6 h-14 border-b border-[var(--owl-border)] bg-[var(--owl-parchment)]/60 backdrop-blur-sm">
      <Link to="/" className="flex items-center gap-2 group">
        <img
          src={owlIcon}
          alt="Home"
          className="h-8 w-8 object-contain transition-transform group-hover:scale-110"
        />
      </Link>
      <span className="text-sm font-semibold tracking-wide text-[var(--owl-brown-deep)]">
        THE NOCTURNAL ATHENAEUM
      </span>
    </header>
  );
}
