# Architecture

```mermaid
flowchart LR
    GH[GitHub App webhooks] --> API[API and admission policy]
    UI[Maintainer dashboard] --> API
    API --> DB[(PostgreSQL and outbox)]
    DB --> WF[Temporal workflow]
    WF --> FETCH[Source and log fetcher]
    WF --> AGENT[Agent and constrained tool router]
    WF --> EXEC[Execution broker]
    EXEC --> PREP[Dependency preparation sandbox]
    EXEC --> EXP[Exploration sandbox]
    EXEC --> VERIFY[Fresh verification sandbox]
    FETCH --> STORE[(Tenant-scoped artifacts)]
    EXEC --> STORE
    WF --> GATE[Evidence and approval gate]
    GATE --> PUB[Publisher]
    PUB --> GHPR[GitHub draft PR]
    CREDS[Credential broker] --> FETCH
    CREDS --> PUB
```

Embedded profile substitutes Temporal with `InvestigationRuntime` and GitHub with `FixtureGitHub`. Those adapters are labeled. Production must bind Temporal workers and the gVisor executor; admission fails closed if `runsc` is missing.
