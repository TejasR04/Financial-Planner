# Gemini AI integration

Meridian's `/api/v1/agent/chat` endpoint uses Google's official `google-genai`
Python SDK. The deterministic financial tools remain provider-independent;
the Gemini adapter only translates function declarations, conversation parts,
and function responses.

## Configuration

Add these values to `backend/.env` (never commit the key):

```dotenv
GEMINI_API_KEY=your-key-here
GEMINI_MODEL=gemini-2.5-flash
```

The API starts without a key, but `/agent/chat` returns HTTP 503 with an
actionable configuration message until `GEMINI_API_KEY` is present. Restart
the API after changing `.env`:

```bash
docker compose -f backend/docker-compose.yml up --build -d
```

## Tool-calling flow

1. The orchestrator sends the user message, history, system instructions, and
   the registered Gemini function declarations.
2. Gemini may return one or more function calls.
3. Meridian validates each call with its Pydantic input model and executes the
   deterministic service-backed tool locally.
4. The serialized results are sent back as Gemini function responses.
5. Gemini produces the final natural-language answer. Financial figures must
   come from tool results, not model estimates.

The provider adapter is in `app/ai/agent.py`; schema conversion and result
serialization are in `app/ai/tool_registry.py`. Provider-free tests use a
fake Gemini client, so they never require a live key.
