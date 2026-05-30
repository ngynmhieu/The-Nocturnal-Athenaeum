"""Pydantic models for chat API."""
from typing import List, Optional
from pydantic import BaseModel, Field


class Message(BaseModel):
    """A single message in the chat history."""
    role: str = Field(..., description="Role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class ChatRequest(BaseModel):
    """Request body for chat endpoint."""
    messages: List[Message] = Field(..., description="Chat history including the latest user message")
    max_tokens: Optional[int] = Field(None, description="Max tokens to generate (uses default if not specified)")
    enable_thinking: Optional[bool] = Field(False, description="Enable extended thinking mode")


class ChatResponse(BaseModel):
    """Response body for chat endpoint."""
    response: str = Field(..., description="Generated assistant response")
    elapsed_time: float = Field(..., description="Time taken to generate response in seconds")
    tokens_generated: Optional[int] = Field(None, description="Number of tokens generated")


class StreamChunk(BaseModel):
    """A single chunk of streamed response."""
    chunk: str = Field(..., description="Token or partial text chunk")
    elapsed_time: Optional[float] = Field(None, description="Elapsed time so far")
