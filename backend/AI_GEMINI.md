# Gemini AI integration

Meridian's `/api/v1/agent/chat` endpoint uses Google's official `google-genai`
Python SDK. The deterministic financial tools remain provider-independent;
the Gemini adapter only translates function declarations, conversation parts,
and function responses.

## Configuration

Add these values to `backend/.env` (never commit the key):

```dotenv
GEMINI_API_KEY=your-key-here
GEMINI_MODEL=gemini-3.6-flash
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

`app/ai/assistant_context.md` is the durable behavior and tool-routing context.
Each request also receives a current financial summary built from the signed-in
user's accounts, planning profile, holdings, debts, income sources, and
trailing transaction totals. Relevant budget and transaction facts are added
when the question calls for them. Meri can also use authenticated, read-only
tools during the conversation to search transactions, calculate complete
spending totals, or retrieve a monthly budget summary. Transaction details
are paged, and the model cannot choose a different user ID.

Conversation messages are stored per user in `agent_messages`; the Insights
view and bottom-right Meri popup share that history and active conversation.
The provider adapter is in
`app/ai/agent.py`; schema conversion and result serialization are in
`app/ai/tool_registry.py`. Provider-free tests use a fake Gemini client, so
they never require a live key.
