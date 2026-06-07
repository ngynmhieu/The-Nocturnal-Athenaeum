import { useState } from "react";
import { useSendMessage } from "../features";
import { ChatTranscript, ChatInput, ChatGreeting } from "../widgets";
import type { Message } from "../entities";

export function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const { isStreaming, sendMessage, stopStreaming } = useSendMessage({ messages, setMessages });

  if (messages.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-screen gap-4">
        <ChatGreeting />
        <ChatInput isStreaming={isStreaming} onSend={sendMessage} onStop={stopStreaming} />
      </div>
    );
  }

  return (
    <div className="relative h-screen">
      <ChatTranscript messages={messages} isStreaming={isStreaming} />
      <div className="absolute bottom-0 left-0 right-0 z-10">
        <ChatInput isStreaming={isStreaming} onSend={sendMessage} onStop={stopStreaming} />
      </div>
    </div>
  );
}
