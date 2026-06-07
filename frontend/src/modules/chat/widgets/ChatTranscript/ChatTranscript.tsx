import { useEffect, useRef } from "react";
import type { Message } from "../../entities";
import { ChatMessage } from "./components/ChatMessage";

interface ChatTranscriptProps {
  messages: Message[];
  isStreaming: boolean;
}

export function ChatTranscript({ messages, isStreaming }: ChatTranscriptProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isStreaming]);

  return (
    <div className="absolute inset-0">
      <div className="h-full overflow-y-auto py-6 pb-40 [scrollbar-gutter:stable_both-edges]">
        <div className="w-full max-w-3xl mx-auto flex flex-col gap-4">
          {messages.map((msg) => <ChatMessage key={msg.id} message={msg} />)}
          <div ref={bottomRef} />
        </div>
      </div>
    </div>
  );
}
