export function TypingIndicator() {
  return (
    <div className="flex justify-start px-4">
      <div className="flex items-center gap-1.5 bg-white/60 backdrop-blur-sm border border-[var(--owl-border)] rounded-2xl rounded-bl-sm px-4 py-3">
        <span
          className="w-2 h-2 rounded-full bg-[var(--owl-brown-muted)] animate-bounce"
          style={{ animationDelay: "0s" }}
        />
        <span
          className="w-2 h-2 rounded-full bg-[var(--owl-brown-muted)] animate-bounce"
          style={{ animationDelay: "0.15s" }}
        />
        <span
          className="w-2 h-2 rounded-full bg-[var(--owl-brown-muted)] animate-bounce"
          style={{ animationDelay: "0.3s" }}
        />
      </div>
    </div>
  );
}
