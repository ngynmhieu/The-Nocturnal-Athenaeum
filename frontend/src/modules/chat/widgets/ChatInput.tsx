import { useState, useRef } from "react";
import { ArrowUpIcon, StopIcon } from "@/shared/ui";

interface ChatInputProps {
  isStreaming: boolean;
  onSend: (content: string) => void;
  onStop: () => void;
}

export function ChatInput({ isStreaming, onSend, onStop }: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = () => {
    const trimmed = value.trim();
    if (!trimmed || isStreaming) return;
    onSend(trimmed);
    setValue("");
    textareaRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="w-full max-w-3xl mx-auto pb-6 pt-2">
      <div
        className="flex items-end gap-3 bg-white/60 backdrop-blur-md border border-[var(--owl-border)] rounded-2xl px-4 py-3 shadow-md cursor-text"
        onClick={() => textareaRef.current?.focus()}
      >
        <textarea
          ref={textareaRef}
          rows={1}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isStreaming}
          placeholder="Ask the Docent anything..."
          className="flex-1 resize-none bg-transparent text-[var(--owl-brown-dark)] placeholder-[var(--owl-brown-muted)] text-base leading-9 outline-none max-h-40 disabled:opacity-50"
          style={{ fieldSizing: "content" } as React.CSSProperties}
        />

        {isStreaming ? (
          <button
            onClick={onStop}
            aria-label="Stop generating"
            className="shrink-0 w-9 h-9 rounded-xl bg-[var(--owl-brown-muted)] hover:bg-[var(--owl-brown-dark)] transition-colors flex items-center justify-center text-[var(--owl-cream)]"
          >
            <StopIcon size={20} />
          </button>
        ) : (
          <button
            onClick={handleSend}
            disabled={!value.trim()}
            aria-label="Send"
            className="shrink-0 w-9 h-9 rounded-xl bg-[var(--owl-brown)] hover:bg-[var(--owl-brown-dark)] disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center justify-center text-[var(--owl-cream)]"
          >
            <ArrowUpIcon size={20} />
          </button>
        )}
      </div>
    </div>
  );
}
