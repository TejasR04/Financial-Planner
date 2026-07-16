"""ToolRegistry — the seam between the LLM and the deterministic backend.

Every tool is registered with a Pydantic input schema and a plain callable
that returns a Pydantic (or dataclass) result. `to_openai_tools()` produces
the JSON-schema tool definitions for an OpenAI-compatible `tools=[...]`
argument. `dispatch()` validates the model's arguments and invokes the
handler — this is the only place tool-calling-protocol details live, so
swapping to MCP later means rewriting this file only, not the tools
themselves.
"""
from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from typing import Any, Callable

from pydantic import BaseModel


class ToolSpec:
    def __init__(self, name: str, description: str, input_model: type[BaseModel], handler: Callable[..., Any]):
        self.name = name
        self.description = description
        self.input_model = input_model
        self.handler = handler

    def to_openai_tool(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_model.model_json_schema(),
            },
        }


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolSpec] = {}

    def register(self, name: str, description: str, input_model: type[BaseModel]):
        def decorator(handler: Callable[..., Any]) -> Callable[..., Any]:
            self._tools[name] = ToolSpec(name, description, input_model, handler)
            return handler
        return decorator

    def to_openai_tools(self) -> list[dict]:
        return [spec.to_openai_tool() for spec in self._tools.values()]

    def dispatch(self, name: str, raw_arguments: str | dict) -> Any:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        spec = self._tools[name]
        args = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
        validated = spec.input_model.model_validate(args)
        return spec.handler(validated)

    def serialize_result(self, result: Any) -> dict:
        """Every tool result must be JSON-serializable so it can be handed
        back to the LLM and, separately, rendered by the frontend."""
        if isinstance(result, BaseModel):
            return result.model_dump(mode="json")
        if is_dataclass(result):
            return json.loads(json.dumps(asdict(result), default=str))
        raise TypeError(f"Tool result of type {type(result)} is not serializable; wrap it in a Pydantic model")


registry = ToolRegistry()
