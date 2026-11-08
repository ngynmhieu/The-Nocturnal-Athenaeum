import { randomUUID } from "@/shared/lib";
import type { Message, MessageStatus, Role } from "./message.types";

export function createMessage(role: Role, content: string, status: MessageStatus = "complete"): Message {
  return {
    id: randomUUID(),
    role,
    content,
    status,
    createdAt: Date.now(),
  };
}

export function updateLastMessage(messages: Message[], patch: Partial<Pick<Message, "content" | "thinking" | "status">>): Message[] {
  if (messages.length === 0) return messages;
  return messages.map((msg, i) =>
    i === messages.length - 1 ? { ...msg, ...patch } : msg
  );
}

/** Append streamed text to the last message's content/thinking. Reads the current
 *  last message internally so callers never index a possibly-empty array (e.g. when
 *  the conversation was swapped mid-stream); no-ops when there is no message. */
export function appendToLastMessage(messages: Message[], delta: { content?: string; thinking?: string }): Message[] {
  if (messages.length === 0) return messages;
  return messages.map((msg, i) => {
    if (i !== messages.length - 1) return msg;
    return {
      ...msg,
      ...(delta.content !== undefined ? { content: msg.content + delta.content } : {}),
      ...(delta.thinking !== undefined ? { thinking: (msg.thinking ?? "") + delta.thinking } : {}),
    };
  });
}