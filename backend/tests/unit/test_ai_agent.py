from types import SimpleNamespace

import pytest

from app.ai.agent import AgentOrchestrator, GeminiConfigurationError
from app.ai import tool_registry
from app.core.config import get_settings


class FakeModels:
    def __init__(self) -> None:
        self.requests = []

    def generate_content(self, **kwargs):
        self.requests.append(kwargs)
        if len(self.requests) == 1:
            call = SimpleNamespace(
                name="calculate_hsa_tax_savings",
                args={"annual_hsa_contribution": 4000, "marginal_federal_rate": 0.24},
                id="call-1",
            )
            part = SimpleNamespace(function_call=call)
            return SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=[part]))], text="")
        return SimpleNamespace(candidates=[], text="Your estimated annual HSA tax savings is $1,096.")


class FakeClient:
    def __init__(self) -> None:
        self.models = FakeModels()


def test_gemini_declarations_are_openapi_subset_and_tools_are_serializable() -> None:
    import app.ai.agent  # noqa: F401 - registers all tool modules

    declarations = tool_registry.registry.to_gemini_declarations()
    assert len(declarations) == 13
    assert all("$defs" not in declaration["parameters"] for declaration in declarations)
    assert tool_registry.registry.serialize_result({"amount": 1}) == {"amount": 1}


def test_gemini_function_call_round_trip() -> None:
    client = FakeClient()
    result = AgentOrchestrator(client=client, model="test-model").handle_message("How much can my HSA save?")

    assert result.reply.startswith("Your estimated annual HSA")
    assert result.tool_calls == [
        {
            "tool": "calculate_hsa_tax_savings",
            "arguments": {"annual_hsa_contribution": 4000, "marginal_federal_rate": 0.24},
        }
    ]
    assert result.structured_results[0]["tool"] == "calculate_hsa_tax_savings"
    assert len(client.models.requests) == 2
    assert client.models.requests[1]["contents"][-1].role == "user"


def test_missing_gemini_key_is_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "gemini_api_key", None)
    with pytest.raises(GeminiConfigurationError, match="GEMINI_API_KEY"):
        AgentOrchestrator()
