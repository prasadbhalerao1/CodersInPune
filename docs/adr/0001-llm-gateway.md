# ADR 0001 — LLM gateway: provider chain with Gemini key rotation

- Status: accepted (2026-11-09)
- Relates to: D6 (PydanticAI behind our own port), D10 (provider via port), guardrail 9

## Context
D10 leaves the model provider open behind a port. The founder chose Gemini as primary with
up to four API keys (free-tier quotas run out), Groq and a local Ollama as fallbacks, and a
deterministic model for CI. D6 already fixes PydanticAI as the agent library behind
`LLMPort`, with no LangGraph or durable-execution add-ons.

## Decision
- `relay.intelligence.llm.Gateway` implements `LLMPort` over PydanticAI. Providers are tried
  in the order of `RELAY_LLM_PROVIDERS` (`gemini`, `groq`, `ollama`; `fake` for local/test).
- Gemini keys are `RELAY_GEMINI_KEY_1` … `RELAY_GEMINI_KEY_4`; default model `gemini-3.5-flash-lite`
  (fast enough for the step time limits; `RELAY_GEMINI_MODEL` overrides). Output schemas avoid
  `maxItems` and `date-time` formats, which Gemini rejects; sizes are capped in code. A key that returns a quota or
  rate-limit error (429) cools down for 60 s and the next key is tried; an auth failure cools
  it for an hour; 5xx/connection errors move on; any other 4xx stops (it would fail anywhere).
  When every key is cooling down, the next provider is tried.
- Only provider, model and key **index** are recorded per run with tokens, duration and an
  estimated cost. Prompts, keys and provider error bodies are never stored or logged.
- Per-call token budget (`UsageLimits`) and wall-clock time limit; per-workspace monthly
  budget enforced by the run engine.
- Agents only receive read-only tools over the run's evidence pool; output is validated and
  persisted as claims/proposals for human review.
- CI uses PydanticAI `FunctionModel` (no network, no paid calls).

## Consequences
- Cooldowns are per process (API and worker each keep their own); acceptable at this scale.
- No new infrastructure. `pydantic-ai-slim[google,groq,openai]` is MIT-licensed and pinned.
