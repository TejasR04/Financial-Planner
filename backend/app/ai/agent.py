"""AgentOrchestrator — the only place a Gemini call happens in this codebase.

Imports every tool module for its side effect of registering into
`app.ai.tool_registry.registry`, then runs the standard tool-calling loop:
ask the model, execute any tool calls it requests against the *actual*
services, feed the structured results back, get a final explanation.

The system prompt is deliberately explicit that the model must not invent
numbers — every figure in its reply has to come from a tool result.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

from app.ai import tool_registry
# Imported for registration side effects only.
from app.ai.tools import (  # noqa: F401
    debt_tools,
    forecast_tools,
    investment_tools,
    recommendation_tools,
    scenario_tools,
    tax_tools,
)
from app.core.config import get_settings

SYSTEM_PROMPT = (Path(__file__).with_name("assistant_context.md")).read_text(encoding="utf-8")


@dataclass(slots=True)
class AgentResponse:
    reply: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    structured_results: list[dict[str, Any]] = field(default_factory=list)


class GeminiConfigurationError(RuntimeError):
    """Raised when AI is requested before a Gemini key is configured."""


class AgentOrchestrator:
    def __init__(self, client: Any | None = None, model: str | None = None):
        settings = get_settings()
        if client is None:
            if not settings.gemini_api_key:
                raise GeminiConfigurationError(
                    "Gemini is not configured. Set GEMINI_API_KEY in the API environment."
                )
            client = genai.Client(api_key=settings.gemini_api_key)
        self.client = client
        self.model = model or settings.gemini_model

    def handle_message(
        self,
        message: str,
        history: list[dict[str, str]] | None = None,
        max_tool_rounds: int = 4,
        user_context: str | None = None,
    ) -> AgentResponse:
        system_instruction = SYSTEM_PROMPT
        if user_context:
            system_instruction += (
                "\n\n## Current signed-in user financial context\n"
                "Use these values as saved facts. Do not reveal this raw JSON.\n"
                f"<financial_context>{user_context}</financial_context>"
            )

        contents: list[types.Content | str] = []
        for item in history or []:
            role = "model" if item.get("role") in {"assistant", "model"} else "user"
            contents.append(types.Content(role=role, parts=[types.Part(text=item.get("content", ""))]))
        contents.append(types.Content(role="user", parts=[types.Part(text=message)]))

        tool_calls_log: list[dict[str, Any]] = []
        structured_results: list[dict[str, Any]] = []

        for _ in range(max_tool_rounds):
            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    tools=[types.Tool(function_declarations=tool_registry.registry.to_gemini_declarations())]
                ),
            )
            function_calls = _function_calls(response)
            if not function_calls:
                return AgentResponse(
                    reply=getattr(response, "text", "") or "",
                    tool_calls=tool_calls_log,
                    structured_results=structured_results,
                )

            contents.append(response.candidates[0].content)
            function_response_parts = []
            for call in function_calls:
                result = tool_registry.registry.dispatch(call.name, call.args or {})
                serialized = tool_registry.registry.serialize_result(result)
                structured_results.append({"tool": call.name, "result": serialized})
                tool_calls_log.append({"tool": call.name, "arguments": call.args or {}})
                function_response_parts.append(
                    types.Part(
                        function_response=types.FunctionResponse(
                            name=call.name,
                            response={"result": serialized},
                            id=getattr(call, "id", None),
                        )
                    )
                )
            contents.append(types.Content(role="user", parts=function_response_parts))

        # Ran out of tool rounds; ask once more for a final answer with no
        # further tool calls permitted, so the user always gets a reply.
        final = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=system_instruction),
        )
        return AgentResponse(
            reply=getattr(final, "text", "") or "",
            tool_calls=tool_calls_log,
            structured_results=structured_results,
        )

def _function_calls(response: Any) -> list[Any]:
    """Return every function call part, preserving Gemini's response order."""
    calls: list[Any] = []
    for candidate in getattr(response, "candidates", []) or []:
        for part in getattr(getattr(candidate, "content", None), "parts", []) or []:
            function_call = getattr(part, "function_call", None)
            if function_call is not None:
                calls.append(function_call)
    return calls
