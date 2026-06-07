import type { Message } from "../../../entities";
import { MarkdownRenderer } from "@/shared/ui";

interface ChatMessageProps {
  message: Message;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === "user";
  const isError = message.status === "error";
  const isStreaming = message.status === "streaming";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`
          max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed
          ${isUser
            ? "bg-[var(--owl-brown)] text-[var(--owl-cream)] rounded-br-sm"
            : isError
              ? "bg-red-100/80 text-red-800 rounded-bl-sm border border-red-200"
              : "bg-white/60 backdrop-blur-sm text-[var(--owl-brown-dark)] rounded-bl-sm border border-[var(--owl-border)]"
          }
        `}
      >
        {isUser || isError ? (
          <p className="whitespace-pre-wrap break-words">{message.content}</p>
        ) : (
          <div className="prose-sm">
            <MarkdownRenderer content={message.content} />
          </div>
        )}
        {isError && (
          <p className="text-xs mt-1 opacity-60">Something went wrong. Please try again.</p>
        )}
      </div>
    </div>
  );
}
