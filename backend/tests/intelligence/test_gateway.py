"""Model gateway: Gemini key rotation on quota, provider fallback, budget, timeout."""

import asyncio
from typing import Any

import pytest
from pydantic import BaseModel
from pydantic_ai.exceptions import ModelAuthenticationError, ModelHTTPError
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models import Model
from pydantic_ai.models.function import AgentInfo, FunctionModel

from relay.config import Settings
from relay.intelligence.llm import Gateway, LLMError

pytestmark = pytest.mark.anyio


class Answer(BaseModel):
    text: str


def settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "database_url": "postgresql+psycopg://relay_app:x@db:5432/relay",
        "workos_client_id": "client_TEST",
        "llm_providers": "gemini,groq",
        "gemini_key_1": "k1",
        "gemini_key_2": "k2",
        "gemini_key_3": "k3",
        "groq_api_key": "g",
    }
    return Settings(_env_file=None, **{**base, **overrides})


def answering(text: str) -> FunctionModel:
    def respond(_: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        tool = info.output_tools[0].name
        return ModelResponse(parts=[ToolCallPart(tool, {"text": text})])

    return FunctionModel(respond, model_name="test")


def failing(error: Exception) -> FunctionModel:
    def respond(_: list[ModelMessage], __: AgentInfo) -> ModelResponse:
        raise error

    return FunctionModel(respond, model_name="test")


@pytest.fixture(autouse=True)
def fresh_cooldowns() -> None:
    Gateway._cooldown.clear()


def factory(models: dict[tuple[str, int], Model], calls: list[tuple[str, int]]) -> Any:
    def build(provider: str, key_index: int) -> Model:
        calls.append((provider, key_index))
        return models[(provider, key_index)]

    return build


async def run(gateway: Gateway, **kw: Any) -> Any:
    return await gateway.run(
        instructions="Answer.", prompt="Q", output_type=Answer, token_budget=10_000, **kw
    )


async def test_quota_rotates_to_the_next_gemini_key_and_cools_the_old_one() -> None:
    calls: list[tuple[str, int]] = []
    quota = ModelHTTPError(429, "gemini-2.5-flash", {"error": "RESOURCE_EXHAUSTED"})
    models: dict[tuple[str, int], Model] = {
        ("gemini", 0): failing(quota),
        ("gemini", 1): answering("from key 2"),
    }
    gateway = Gateway(settings(), factory(models, calls))
    result = await run(gateway)
    assert (result.output.text, result.provider, result.key_index) == ("from key 2", "gemini", 1)
    assert calls == [("gemini", 0), ("gemini", 1)]

    calls.clear()
    await run(gateway)  # key 1 is cooling down: not tried again
    assert calls == [("gemini", 1)]


async def test_all_keys_exhausted_falls_back_to_the_next_provider() -> None:
    calls: list[tuple[str, int]] = []
    quota = ModelHTTPError(429, "gemini-2.5-flash")
    models: dict[tuple[str, int], Model] = {
        ("gemini", 0): failing(quota),
        ("gemini", 1): failing(ModelAuthenticationError("gemini-2.5-flash", "bad key")),
        ("gemini", 2): failing(ModelHTTPError(503, "gemini-2.5-flash")),
        ("groq", 0): answering("from groq"),
    }
    result = await run(Gateway(settings(), factory(models, calls)))
    assert (result.output.text, result.provider, result.model) == (
        "from groq",
        "groq",
        "llama-3.3-70b-versatile",
    )
    assert calls == [("gemini", 0), ("gemini", 1), ("gemini", 2), ("groq", 0)]


async def test_every_provider_failing_is_a_transient_error_without_provider_text() -> None:
    quota = ModelHTTPError(429, "m", {"error": "secret-ish provider body"})
    models: dict[tuple[str, int], Model] = {("gemini", i): failing(quota) for i in range(3)}
    models[("groq", 0)] = failing(quota)
    with pytest.raises(LLMError) as error:
        await run(Gateway(settings(), factory(models, [])))
    assert (error.value.code, error.value.transient) == ("quota_exhausted", True)
    assert "secret" not in str(error.value)


async def test_a_bad_request_is_not_retried_elsewhere() -> None:
    calls: list[tuple[str, int]] = []
    models: dict[tuple[str, int], Model] = {("gemini", 0): failing(ModelHTTPError(400, "m"))}
    with pytest.raises(LLMError, match="provider_rejected_400"):
        await run(Gateway(settings(), factory(models, calls)))
    assert calls == [("gemini", 0)]


async def test_token_budget_and_timeout_stop_the_call() -> None:
    models: dict[tuple[str, int], Model] = {("gemini", 0): answering("x" * 400)}
    gateway = Gateway(settings(), factory(models, []))
    with pytest.raises(LLMError, match="token_budget_exceeded"):
        await gateway.run(instructions="A", prompt="Q", output_type=Answer, token_budget=5)

    async def slow(_: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        await asyncio.sleep(2)
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {"text": "late"})])

    late: dict[tuple[str, int], Model] = {("gemini", 0): FunctionModel(slow)}
    with pytest.raises(LLMError, match="timeout"):
        await run(Gateway(settings(), factory(late, [])), time_limit=0.2)


def test_no_providers_means_ai_is_off_and_config_is_validated() -> None:
    assert not Gateway(settings(llm_providers=None)).configured
    assert Gateway(settings()).configured
    with pytest.raises(ValueError, match="RELAY_GEMINI_KEY_1"):
        settings(gemini_key_1=None, gemini_key_2=None, gemini_key_3=None)
    with pytest.raises(ValueError, match="unknown provider"):
        settings(llm_providers="openai")
    with pytest.raises(ValueError, match="fake provider"):
        settings(llm_providers="fake", environment="production")


def test_tool_calls_are_recorded_by_name_only() -> None:
    from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart

    from relay.intelligence.llm import _tool_calls

    messages = [
        ModelResponse(parts=[ToolCallPart("search_evidence", {"query": "secret text"})]),
        ModelResponse(parts=[TextPart("x"), ToolCallPart("get_evidence", {"ref": "E1"})]),
        ModelResponse(parts=[ToolCallPart("final_result", {"claims": []})]),
    ]
    assert _tool_calls(messages) == ("search_evidence", "get_evidence")  # type: ignore[arg-type]


def test_unknown_models_use_configured_prices() -> None:
    from decimal import Decimal

    from relay.intelligence.llm import cost_of

    assert cost_of("gemini-2.5-flash-lite", 1_000_000, 0) == Decimal("0.10")
    assert cost_of("new-model", 1_000_000, 1_000_000) == 0
    assert cost_of("new-model", 2_000_000, 1_000_000, (Decimal("0.1"), Decimal("0.4"))) == Decimal(
        "0.6"
    )
