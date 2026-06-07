import type { Message, MessageStatus, Role } from "./message.types";

export function createMessage(role: Role, content: string, status: MessageStatus = "complete"): Message {
  return {
    id: crypto.randomUUID(),
    role,
    content,
    status,
    createdAt: Date.now(),
  };
}

export function updateLastMessage(messages: Message[], patch: Partial<Pick<Message, "content" | "status">>): Message[] {
  if (messages.length === 0) return messages;
  return messages.map((msg, i) =>
    i === messages.length - 1 ? { ...msg, ...patch } : msg
  );
}