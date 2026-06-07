interface ScrollToBottomProps {
  onClick: () => void;
}

export function ScrollToBottom({ onClick }: ScrollToBottomProps) {
  return (
    <button
      onClick={onClick}
      aria-label="Scroll to bottom"
      className="absolute bottom-6 right-6 w-9 h-9 rounded-full bg-[var(--owl-brown)] hover:bg-[var(--owl-brown-dark)] text-[var(--owl-cream)] shadow-lg flex items-center justify-center transition-colors"
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="w-4 h-4"
      >
        <path d="M12 5v14M5 12l7 7 7-7" />
      </svg>
    </button>
  );
}
