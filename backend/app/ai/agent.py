"""AgentOrchestrator — the only place an LLM call happens in this codebase.

Imports every tool module for its side effect of registering into
`app.ai.tool_registry.registry`, then runs the standard tool-calling loop:
ask the model, execute any tool calls it requests against the *actual*
services, feed the structured results back, get a final explanation.

The system prompt is deliberately explicit that the model must not invent
numbers — every figure in its reply has to come from a tool result.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from openai import OpenAI

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

SYSTEM_PROMPT = """You are Meridian's financial planning assistant.

You never compute balances, taxes, investment growth, amortization
schedules, or retirement projections yourself. For any question that
requires a number, call the appropriate tool and base your answer only on
the structured result it returns. If no tool covers the question, say so
rather than estimating.

When you have a result, explain it in plain language: state the numbers
from the tool result, and briefly say what's driving them. Do not invent
figures, and do not restate the user's numbers as if they were computed
unless a tool actually returned them."""


@dataclass(slots=True)
class AgentResponse:
    reply: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    structured_results: list[dict[str, Any]] = field(default_factory=list)


class AgentOrchestrator:
    def __init__(self, client: OpenAI | None = None, model: str | None = None):
        settings = get_settings()
        self.client = client or OpenAI(api_key=settings.openai_api_key)
        self.model = model or settings.openai_model

    def handle_message(
        self, message: str, history: list[dict[str, str]] | None = None, max_tool_rounds: int = 4
    ) -> AgentResponse:
        messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(history or [])
        messages.append({"role": "user", "content": message})

        tool_calls_log: list[dict[str, Any]] = []
        structured_results: list[dict[str, Any]] = []

        for _ in range(max_tool_rounds):
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tool_registry.registry.to_openai_tools(),
            )
            choice = completion.choices[0]
            messages.append(choice.message.model_dump(exclude_none=True))

            if not choice.message.tool_calls:
                return AgentResponse(
                    reply=choice.message.content or "",
                    tool_calls=tool_calls_log,
                    structured_results=structured_results,
                )

            for call in choice.message.tool_calls:
                result = tool_registry.registry.dispatch(call.function.name, call.function.arguments)
                serialized = tool_registry.registry.serialize_result(result)
                structured_results.append({"tool": call.function.name, "result": serialized})
                tool_calls_log.append({"tool": call.function.name, "arguments": call.function.arguments})
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": _to_json(serialized),
                    }
                )

        # Ran out of tool rounds; ask once more for a final answer with no
        # further tool calls permitted, so the user always gets a reply.
        final = self.client.chat.completions.create(model=self.model, messages=messages)
        return AgentResponse(
            reply=final.choices[0].message.content or "",
            tool_calls=tool_calls_log,
            structured_results=structured_results,
        )


def _to_json(value: Any) -> str:
    import json

    return json.dumps(value, default=str)
