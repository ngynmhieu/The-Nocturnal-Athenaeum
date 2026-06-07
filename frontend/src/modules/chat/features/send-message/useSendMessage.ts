import { useCallback, useRef, useState } from "react";
import { chatApi } from "@/shared/api";
import { createMessage, updateLastMessage } from "../../entities";
import type { Message } from "../../entities";

interface UseSendMessageProps {
  messages: Message[];
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
}

interface UseSendMessageReturn {
  isStreaming: boolean;
  sendMessage: (content: string) => Promise<void>;
  stopStreaming: () => void;
}

export function useSendMessage({ messages, setMessages }: UseSendMessageProps): UseSendMessageReturn {
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const sendMessage = useCallback(async (content: string) => {
    if (isStreaming) return;

    const userMessage = createMessage("user", content, "complete");
    const assistantMessage = createMessage("assistant", "", "streaming");

    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setIsStreaming(true);
    abortRef.current = new AbortController();

    try {
      const history = messages.map((m) => ({ role: m.role, content: m.content }));

      for await (const chunk of chatApi.stream(
        {
          messages: [...history, { role: "user", content }],
          max_tokens: 1024,
          enable_thinking: false,
        },
        abortRef.current.signal
      )) {
        if (chunk.error) throw new Error(chunk.error);

        if (chunk.chunk) {
          setMessages((prev) =>
            updateLastMessage(prev, { content: prev[prev.length - 1].content + chunk.chunk })
          );
        }
      }

      setMessages((prev) => updateLastMessage(prev, { status: "complete" }));
    } catch (err) {
      if ((err as Error).name === "AbortError") {
        setMessages((prev) => updateLastMessage(prev, { status: "complete" }));
      } else {
        setMessages((prev) => updateLastMessage(prev, { status: "error" }));
      }
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
    }
  }, [isStreaming, messages, setMessages]);

  return { isStreaming, sendMessage, stopStreaming };
}
