"""ToolRegistry — the seam between Gemini and the deterministic backend.

Every tool is registered with a Pydantic input schema and a plain callable
that returns a Pydantic (or dataclass) result. `to_gemini_declarations()`
produces the JSON-schema function declarations used by Google's function
calling API. `dispatch()` validates the model's arguments and invokes the
handler, keeping the deterministic tools provider agnostic.
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

    def to_gemini_declaration(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": _clean_gemini_schema(self.input_model.model_json_schema()),
        }


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolSpec] = {}

    def register(self, name: str, description: str, input_model: type[BaseModel]):
        def decorator(handler: Callable[..., Any]) -> Callable[..., Any]:
            self._tools[name] = ToolSpec(name, description, input_model, handler)
            return handler
        return decorator

    def to_gemini_declarations(self) -> list[dict]:
        return [spec.to_gemini_declaration() for spec in self._tools.values()]

    def dispatch(self, name: str, raw_arguments: str | dict) -> Any:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        spec = self._tools[name]
        args = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
        validated = spec.input_model.model_validate(args)
        return spec.handler(validated)

    def serialize_result(self, result: Any) -> Any:
        """Every tool result must be JSON-serializable so it can be handed
        back to the LLM and, separately, rendered by the frontend."""
        if isinstance(result, BaseModel):
            return result.model_dump(mode="json")
        if is_dataclass(result):
            return json.loads(json.dumps(asdict(result), default=str))
        if isinstance(result, (dict, list, tuple, str, int, float, bool)) or result is None:
            return json.loads(json.dumps(result, default=str))
        raise TypeError(f"Tool result of type {type(result)} is not serializable; wrap it in a Pydantic model")


registry = ToolRegistry()


def _clean_gemini_schema(schema: dict) -> dict:
    """Resolve Pydantic schema metadata into Gemini's supported subset."""
    definitions = schema.get("$defs", {})

    def normalize(value: object) -> object:
        if not isinstance(value, dict):
            return value
        if "$ref" in value:
            name = value["$ref"].rsplit("/", 1)[-1]
            return normalize(definitions.get(name, {"type": "object"}))
        if "anyOf" in value:
            options = [option for option in value["anyOf"] if option != {"type": "null"}]
            return normalize(options[0] if options else {"type": "string"})

        cleaned: dict[str, object] = {}
        for key, child in value.items():
            if key in {"$defs", "$schema", "title", "default", "additionalProperties"}:
                continue
            if key == "properties" and isinstance(child, dict):
                cleaned[key] = {name: normalize(item) for name, item in child.items()}
            elif key in {"items", "not", "contains"}:
                cleaned[key] = normalize(child)
            else:
                cleaned[key] = child
        return cleaned

    result = normalize(schema)
    return result if isinstance(result, dict) else {"type": "object"}
