"""Model gateway (D6, D10; ADR 0001): our own `LLMPort` over PydanticAI.

Providers are tried in the order of RELAY_LLM_PROVIDERS. Gemini may have up to four API
keys: a key that hits its quota or rate limit cools down and the next key is used; when
every key of a provider is cooling down or failing, the next provider is tried. Only the
provider, model and key *index* are ever recorded; prompts and keys are never logged.

Agents built here receive read-only tools only (`relay.intelligence.tools`), so a model
can never change anything: its output is validated and becomes claims or proposals.
"""

import asyncio
import os
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

from pydantic_ai import Agent, Tool
from pydantic_ai.exceptions import (
    ModelAPIError,
    ModelAuthenticationError,
    ModelHTTPError,
    ModelQuotaExceededError,
    ModelRateLimitError,
    UnexpectedModelBehavior,
    UsageLimitExceeded,
)
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models import Model
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.usage import UsageLimits

from relay.config import Settings

# Relay logs no prompts; keep PydanticAI's console banner out of API and worker logs.
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

# USD per million tokens (input, output). Unknown models cost 0 (reported, not enforced).
PRICES: dict[str, tuple[Decimal, Decimal]] = {
    "gemini-2.5-flash": (Decimal("0.30"), Decimal("2.50")),
    "gemini-2.5-flash-lite": (Decimal("0.10"), Decimal("0.40")),
    "gemini-2.5-pro": (Decimal("1.25"), Decimal("10.00")),
    "llama-3.3-70b-versatile": (Decimal("0.59"), Decimal("0.79")),
}
QUOTA_COOLDOWN_SECONDS = 60.0
AUTH_COOLDOWN_SECONDS = 3600.0

FakeHandler = Callable[[list[ModelMessage], AgentInfo], ModelResponse]
ModelFactory = Callable[[str, int], Model]


class LLMError(Exception):
    """A classified failure; `code` is safe to store and show (no provider text)."""

    def __init__(self, code: str, *, transient: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.transient = transient


@dataclass(frozen=True)
class LLMResult[T]:
    output: T
    provider: str
    model: str
    key_index: int
    input_tokens: int
    output_tokens: int
    duration_ms: int
    cost_usd: Decimal
    # Names of the evidence tools the model called, in order (never their arguments).
    tool_calls: tuple[str, ...] = ()


def _tool_calls(messages: list[ModelMessage]) -> tuple[str, ...]:
    return tuple(
        part.tool_name
        for message in messages
        if isinstance(message, ModelResponse)
        for part in message.parts
        if isinstance(part, ToolCallPart) and not part.tool_name.startswith("final_result")
    )


class LLMPort(Protocol):
    @property
    def configured(self) -> bool: ...

    async def run[T](
        self,
        *,
        instructions: str,
        prompt: str,
        output_type: type[T],
        tools: Sequence[Tool[Any]] = (),
        deps: Any = None,
        token_budget: int,
        time_limit: float | None = None,
    ) -> LLMResult[T]: ...


def cost_of(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    price_in, price_out = PRICES.get(model, (Decimal(0), Decimal(0)))
    return (price_in * input_tokens + price_out * output_tokens) / 1_000_000


# Test/local hook: the "fake" provider answers with this function (see tests/intelligence).
fake_handler: FakeHandler | None = None


def _fake(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    if fake_handler is None:
        raise LLMError("fake_provider_without_handler")
    return fake_handler(messages, info)


def default_model_factory(settings: Settings) -> ModelFactory:
    def build(provider: str, key_index: int) -> Model:
        if provider == "gemini":
            from pydantic_ai.models.google import GoogleModel
            from pydantic_ai.providers.google import GoogleProvider

            key = settings.gemini_keys[key_index].get_secret_value()
            return GoogleModel(settings.gemini_model, provider=GoogleProvider(api_key=key))
        if provider == "groq":
            from pydantic_ai.models.groq import GroqModel
            from pydantic_ai.providers.groq import GroqProvider

            assert settings.groq_api_key is not None
            key = settings.groq_api_key.get_secret_value()
            return GroqModel(settings.groq_model, provider=GroqProvider(api_key=key))
        if provider == "ollama":
            from pydantic_ai.models.openai import OpenAIChatModel
            from pydantic_ai.providers.ollama import OllamaProvider

            assert settings.ollama_model
            return OpenAIChatModel(
                settings.ollama_model, provider=OllamaProvider(base_url=settings.ollama_url)
            )
        if provider == "fake":
            return FunctionModel(_fake, model_name="fake")
        raise LLMError("unknown_provider")

    return build


class Gateway:
    """`LLMPort` over the configured provider chain with per-key cooldowns."""

    # Process-wide: a key that ran out of quota stays cooled down across runs.
    _cooldown: dict[tuple[str, int], float] = {}

    def __init__(self, settings: Settings, factory: ModelFactory | None = None) -> None:
        self._settings = settings
        self._factory = factory or default_model_factory(settings)
        self._slots: list[tuple[str, int]] = []
        for provider in settings.llm_provider_list:
            keys = len(settings.gemini_keys) if provider == "gemini" else 1
            self._slots.extend((provider, i) for i in range(keys))

    @property
    def configured(self) -> bool:
        return bool(self._slots)

    def _model_name(self, provider: str) -> str:
        s = self._settings
        names = {"gemini": s.gemini_model, "groq": s.groq_model, "ollama": s.ollama_model}
        return names.get(provider) or provider

    async def run[T](
        self,
        *,
        instructions: str,
        prompt: str,
        output_type: type[T],
        tools: Sequence[Tool[Any]] = (),
        deps: Any = None,
        token_budget: int,
        time_limit: float | None = None,
    ) -> LLMResult[T]:
        if not self._slots:
            raise LLMError("ai_not_configured")
        deadline = time.monotonic() + (time_limit or self._settings.llm_timeout_seconds)
        last = "providers_unavailable"
        for slot in self._slots:
            if self._cooldown.get(slot, 0.0) > time.monotonic():
                last = "quota_exhausted"
                continue
            provider, key_index = slot
            agent: Agent[Any, T] = Agent(
                self._factory(provider, key_index),
                output_type=output_type,
                instructions=instructions,
                tools=list(tools),
                retries=2,
            )
            started = time.monotonic()
            remaining = deadline - started
            if remaining <= 0:
                raise LLMError("timeout", transient=True)
            try:
                async with asyncio.timeout(remaining):
                    result = await agent.run(
                        prompt,
                        deps=deps,
                        usage_limits=UsageLimits(total_tokens_limit=token_budget),
                    )
            except TimeoutError:
                raise LLMError("timeout", transient=True) from None
            except UsageLimitExceeded:
                raise LLMError("token_budget_exceeded") from None
            except ModelQuotaExceededError, ModelRateLimitError:
                self._cooldown[slot] = time.monotonic() + QUOTA_COOLDOWN_SECONDS
                last = "quota_exhausted"
                continue
            except ModelAuthenticationError:
                self._cooldown[slot] = time.monotonic() + AUTH_COOLDOWN_SECONDS
                last = "provider_auth_failed"
                continue
            except ModelHTTPError as error:
                if error.status_code == 429:
                    self._cooldown[slot] = time.monotonic() + QUOTA_COOLDOWN_SECONDS
                    last = "quota_exhausted"
                    continue
                if error.status_code in (401, 403):
                    self._cooldown[slot] = time.monotonic() + AUTH_COOLDOWN_SECONDS
                    last = "provider_auth_failed"
                    continue
                if error.status_code >= 500:
                    last = "provider_unavailable"
                    continue
                raise LLMError(f"provider_rejected_{error.status_code}") from None
            except ModelAPIError:
                last = "provider_unavailable"
                continue
            except UnexpectedModelBehavior:
                raise LLMError("invalid_model_output") from None
            usage = result.usage
            model = self._model_name(provider)
            return LLMResult(
                output=result.output,
                provider=provider,
                model=model,
                key_index=key_index,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                duration_ms=int((time.monotonic() - started) * 1000),
                cost_usd=cost_of(model, usage.input_tokens, usage.output_tokens),
                tool_calls=_tool_calls(result.all_messages()),
            )
        raise LLMError(last, transient=True)
