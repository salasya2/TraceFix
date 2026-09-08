# ADR 0005 — Provider interface with Anthropic default for live calls

## Decision

`ModelProvider` is the only model boundary. Implementations:

- `FixtureProvider` — labeled simulated, uses the real tool router (default for tests/demo).
- `AnthropicProvider` — Anthropic SDK, `ANTHROPIC_API_KEY`, default model `claude-sonnet-5`.
- `SpaceXAIProvider` — optional OpenAI-compatible client, `XAI_API_KEY`, `https://api.x.ai/v1`.

Deterministic code owns access, budgets, tests, and publication. LLM confidence is not a release gate.

## Alternatives

- SpaceXAI/Grok as the live default: rejected; the product spec and operator preference pin Anthropic for live diagnosis.
- Embeddings/vector DB in v1: deferred until an eval shows improvement at acceptable cost.
