import { useCallback, useState } from "react";
import { useParams, useLocation } from "react-router";
import { motion, AnimatePresence } from "motion/react";
import { useModels } from "../shared";
import { useChatSession } from "../entities";
import { useSendMessage } from "../features";
import { ChatTranscript, ChatTranscriptSkeleton, ChatInput, ChatGreeting } from "../widgets";

export function ChatPage() {
  // Always present: ChatPage only renders under /c/:conversationId ("/" redirects in).
  const { conversationId } = useParams();
  const routeId = conversationId as string;
  // Set by NewChatRedirect for a freshly minted chat → skip the history fetch.
  const location = useLocation();
  const isNew = (location.state as { isNew?: boolean } | null)?.isNew ?? false;

  const [thinkingEnabled, setThinkingEnabled] = useState(false);
  const [selectedModel, setSelectedModel] = useState<string | null>(null);
  const { models, count: modelCount } = useModels();
  const effectiveModel = selectedModel ?? models.find((m) => m.loaded)?.id ?? models[0]?.id ?? null;

  // A view onto this one conversation's session; the send workflow is separate.
  const { messages, status } = useChatSession(routeId, isNew);
  const { send, stop } = useSendMessage(routeId);

  const isStreaming = status === "streaming";
  const isLoading = status === "loading";
  const hasMessages = messages.length > 0;

  const handleSend = useCallback(
    (content: string) => send({ content, model: effectiveModel, enableThinking: thinkingEnabled }),
    [send, effectiveModel, thinkingEnabled]
  );
  const toggleThinking = () => setThinkingEnabled((v) => !v);

  return (
    // Chat keeps its own scroll box (message list + pinned input), so on a phone
    // — where the layout doesn't fix a height — size it to the screen under the
    // 3.5rem header.
    <div className="relative h-[calc(100dvh-3.5rem)] overflow-hidden md:h-full">
      {/* Empty state: greeting + input centered; exits with fade and slide up.
          Suppressed while history is loading so the greeting doesn't flash. */}
      <AnimatePresence>
        {!hasMessages && !isLoading && (
          <motion.div
            key="empty-state"
            className="absolute inset-0 flex flex-col items-center justify-center gap-4 mb-20"
            exit={{ opacity: 0, y: -16, transition: { duration: 0.2 } }}
          >
            <ChatGreeting modelCount={modelCount} />
            <motion.div layoutId="chat-input" className="w-full">
              <ChatInput
                isStreaming={isStreaming}
                thinkingEnabled={thinkingEnabled}
                onToggleThinking={toggleThinking}
                models={models}
                selectedModel={effectiveModel}
                onSelectModel={setSelectedModel}
                onSend={handleSend}
                onStop={stop}
              />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Loading state: skeleton transcript while history is fetched (no messages yet). */}
      <AnimatePresence>
        {!hasMessages && isLoading && (
          <motion.div
            key="skeleton"
            className="absolute inset-0"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0, transition: { duration: 0.15 } }}
            transition={{ duration: 0.2 }}
          >
            <ChatTranscriptSkeleton />
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
            <ChatInput
              isStreaming={isStreaming}
              thinkingEnabled={thinkingEnabled}
              onToggleThinking={toggleThinking}
              models={models}
              selectedModel={effectiveModel}
              onSelectModel={setSelectedModel}
              onSend={handleSend}
              onStop={stop}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
