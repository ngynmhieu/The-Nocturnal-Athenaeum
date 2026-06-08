const BASE_URL = "/api/v1";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatRequest {
  messages: ChatMessage[];
  max_tokens?: number;
  enable_thinking?: boolean;
}

export interface ChatResponse {
  response: string;
  elapsed_time: number;
}

export interface StreamChunk {
  chunk?: string;
  error?: string;
}

export const chatApi = {
  async *stream(
    body: ChatRequest,
    signal?: AbortSignal
  ): AsyncGenerator<StreamChunk> {
    const res = await fetch(`${BASE_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });

    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(error.detail ?? "Stream request failed");
    }

    const reader = res.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const json = line.slice(6).trim();
          if (json) yield JSON.parse(json) as StreamChunk;
        }
        if (line.startsWith("event: error")) {
          // next line will be the data
        }
      }
    }
  },
};
