import { useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { useSendMessage } from "../features";
import { ChatTranscript, ChatInput, ChatGreeting } from "../widgets";
import type { Message } from "../entities";

export function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const { isStreaming, sendMessage, stopStreaming } = useSendMessage({ messages, setMessages });
  const hasMessages = messages.length > 0;

  return (
    <div className="relative h-full overflow-hidden">

      {/* Empty state: greeting + input centered; exits with fade and slide up */}
      <AnimatePresence>
        {!hasMessages && (
          <motion.div
            key="empty-state"
            className="absolute inset-0 flex flex-col items-center justify-center gap-4"
            exit={{ opacity: 0, y: -16, transition: { duration: 0.2 } }}
          >
            <ChatGreeting />
            <motion.div layoutId="chat-input" className="w-full">
              <ChatInput isStreaming={isStreaming} onSend={sendMessage} onStop={stopStreaming} />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Active state: transcript fades in, input slides from centered to bottom */}
      <AnimatePresence>
        {hasMessages && (
          <motion.div
            key="transcript"
            className="absolute inset-0"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.25 }}
          >
            <ChatTranscript messages={messages} isStreaming={isStreaming} />
          </motion.div>
        )}
        {hasMessages && (
          <motion.div
            key="input-bottom"
            layoutId="chat-input"
            className="absolute bottom-0 inset-x-0 z-10"
            transition={{ type: "spring", stiffness: 350, damping: 35 }}
          >
            <ChatInput isStreaming={isStreaming} onSend={sendMessage} onStop={stopStreaming} />
          </motion.div>
        )}
      </AnimatePresence>

    </div>
  );
}
