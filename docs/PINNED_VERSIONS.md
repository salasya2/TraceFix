# Pinned versions

Do not use floating `latest` tags in deployment or benchmark manifests.

| Component | Pin |
|---|---|
| GitHub REST API | `2022-11-28` |
| Python runtime profiles | 3.11, 3.12, 3.13 (default profile `python312-pytest-v1`) |
| FastAPI | 0.115.8 |
| Pydantic | 2.10.6 |
| SQLAlchemy | 2.0.38 |
| Alembic | 1.14.1 |
| Temporal Python SDK | 1.8.0 |
| Anthropic SDK | 0.43.1 |
| OpenAI-compatible client (SpaceXAI) | 1.61.1 |
| Default SpaceXAI model | `grok-4.5` |
| Prompt version | `v1` |
| React | 18.3.1 |
| Vite | 6.0.11 |
| TypeScript | 5.7.3 |
| PostgreSQL (compose) | 17.4 |
| Python container image | `python:3.12.8-bookworm` (record digest at image build) |

Upgrade policy: bump one dependency family per change, run `python scripts/tf.py test all` and `eval --split development`, and record the digest in this file.
