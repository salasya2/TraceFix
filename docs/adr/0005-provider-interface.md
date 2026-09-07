# ADR 0005 — Provider interface with SpaceXAI default for live calls

## Decision

`ModelProvider` is the only model boundary. Implementations:

- `FixtureProvider` — labeled simulated, uses the real tool router (default for tests/demo).
- `SpaceXAIProvider` — OpenAI-compatible client, `XAI_API_KEY`, `https://api.x.ai/v1`, model `grok-4.5`.
- `AnthropicProvider` — Anthropic SDK as specified for the control-plane design.

Deterministic code owns access, budgets, tests, and publication. LLM confidence is not a release gate.

## Alternatives

- Embeddings/vector DB in v1: deferred until an eval shows improvement at acceptable cost.
