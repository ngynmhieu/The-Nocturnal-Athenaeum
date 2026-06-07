# The Nocturnal Athenaeum - Backend

FastAPI-based backend service for The Nocturnal Athenaeum chat application.

## Setup

The backend uses a local virtual environment. To run the backend:

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

Or simply run the provided batch script from the project root:

```bash
run_backend.bat
```

This will automatically create the virtual environment and install dependencies on first run.

## How to Use This App

The backend exposes a FastAPI service with the following endpoints:

### 1. Health Check

Check if the service is running and initialized:

```bash
curl http://localhost:8000/api/v1/health
```

**Response:**
```json
{
  "status": "healthy"
}
```

### 2. Chat Request (Single Response)

Send a message and receive a complete response:

**CMD:**
```cmd
curl -X POST http://localhost:8000/api/v1/chat -H "Content-Type: application/json" -d "{\"messages\":[{\"role\":\"user\",\"content\":\"What is the meaning of life?\"}],\"max_tokens\":1024,\"enable_thinking\":false}"
```

**Response:**
```json
{
  "response": "The meaning of life is...",
  "elapsed_time": 2.5
}
```

### 3. Chat Stream (Streaming Response)

Send a message and receive streamed responses:

**CMD:**
```cmd
curl -X POST http://localhost:8000/api/v1/chat/stream -H "Content-Type: application/json" -d "{\"messages\":[{\"role\":\"user\",\"content\":\"What is the meaning of life?\"}],\"max_tokens\":1024,\"enable_thinking\":false}"
```

**Response (Server-Sent Events):**
```
data: {"chunk": "The"}
data: {"chunk": " meaning"}
data: {"chunk": " of"}
...
```

## Request Parameters

- **messages** (required): Array of message objects with `role` and `content` fields
  - `role`: "user" or "assistant"
  - `content`: The message text
- **max_tokens** (optional): Maximum tokens to generate (default: 1024)
- **enable_thinking** (optional): Enable internal reasoning (default: false)

## Requirements

See `requirements.txt` for all dependencies. Main packages:
- FastAPI
- Uvicorn
- Transformers
- Torch
- BitsAndBytes
