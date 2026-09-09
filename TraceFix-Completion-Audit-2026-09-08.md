# TraceFix completion audit

Reviewed September 8, 2026. Repository: [salasya2/TraceFix](https://github.com/salasya2/TraceFix).

Audited revision: [`e42df1bce51e499c6ad59089811e5cbd819c1677`](https://github.com/salasya2/TraceFix/commit/e42df1bce51e499c6ad59089811e5cbd819c1677), committed September 7, 2026, message `switched model`.

## Verdict

**The enterprise specification is not complete. The repository demonstrates a working embedded prototype, but its live workflow and several required safety boundaries remain unimplemented or incorrectly connected.** Adding credentials or provisioning a Linux execution pool alone will not resolve the gaps.

There is useful implementation: domain schemas, policy helpers, database models, an API, a basic React UI, a fixture-backed investigation flow, a verifier that executes pytest, and local tests. Documentation correctly labels the project a scoped pilot in places. However, `PROGRESS.md` overstates completion of durable ingestion, live agent integration, identity, publishing, and operations.

This is a review of the pinned revision, not a claim about later commits. No source fixes or remote GitHub mutations were made. Audit code, temporary state, test reports and a frontend build were created only in the isolated review workspace.

## What was verified

The repository was cloned into an isolated folder. Its Python tests were run against the cloned source using the existing local Python 3.13.7 environment; sampled critical package versions match the repository pins. Frontend dependencies were installed using its frozen pnpm lockfile with lifecycle scripts disabled.

| Check | Observed result | Meaning |
|---|---|---|
| Existing Python suite | **32 passed in 19.00 seconds** | The supplied tests pass; their fixture-based scope is limited |
| Frontend `pnpm run build` | **Passed** | TypeScript checking and Vite production compilation succeed |
| Ruff on packages/apps/services/tests/src/scripts | **Failed: 91 findings** | Formatting/import and other static-check cleanup remains |
| `python scripts/tf.py demo` | **Passed; AWAITING_APPROVAL, simulated=True** | Owned fixture reaches a verified candidate using a supplied answer |
| Production-mode auth probe | **Failed boundary** | Email bearer and email-only login both return HTTP 200; bearer gets owner role |
| Publisher probe | **Failed behavior** | Reports draft PR #1, but branch remains at original SHA; zero blobs/trees/commits created |
| Candidate execution probe | **Failed verification** | Actual child process exits 7; verifier returns verified=True, badge=full |
| Alembic migration with configured async dialect | **Failed: MissingGreenlet** | Online migrations use a synchronous engine with an async driver |

Windows sandbox restrictions initially blocked pytest temporary-directory access and Vite's compiler subprocess. Those commands were rerun with approval and completed; the initial permission errors are not counted as repository failures.

No live GitHub App, paid model calls, production gVisor containment, PostgreSQL RLS deployment, Temporal cluster, cloud deployment, or browser-interaction test was executed. Where those areas are marked incomplete below, the report identifies concrete source-code gaps rather than treating lack of external access as proof of failure.

## Critical findings

### 1. [P1] Production authentication can be bypassed using a seeded email

`get_principal` treats a bearer token as a seed-user email before considering authentication mode. The email-only development login endpoint also has no development-mode guard. The normal server startup supplies the seeded principals.

**Reproduced:** with `TRACEFIX_ENV=production` and `TRACEFIX_AUTH_MODE=oidc`, anonymous `/v1/auth/me` returned 401, but `Authorization: Bearer maintainer@tracefix.local` returned 200 with role `owner`. Email-only `/v1/auth/login` returned 200. There is no OIDC callback route.

Evidence: [bearer lookup](https://github.com/salasya2/TraceFix/blob/e42df1bce51e499c6ad59089811e5cbd819c1677/apps/api/src/tracefix/api/deps.py#L35-L49), [development login](https://github.com/salasya2/TraceFix/blob/e42df1bce51e499c6ad59089811e5cbd819c1677/apps/api/src/tracefix/api/routes/auth_routes.py#L20-L29).

**Required fix:** completely disable fixture identities outside explicit development mode, reject unsafe startup configuration, and finish OIDC code exchange, signature verification, stored state/nonce checks, membership mapping and session issuance. Test real production-mode routes, not only claim-validation helpers.

### 2. [P1] Candidate verification runs outside the configured sandbox boundary

The investigation runner calls `verify_candidate` directly, which invokes the host Python interpreter through `subprocess.run`. Agent test requests follow the same route. Even the Docker adapter collects tests by calling the host harness afterward. The environment is copied and only a few named secrets are removed.

**Impact:** processing an untrusted repository can execute its imports, `conftest.py`, and candidate code with control-plane filesystem/network access. Selecting a container adapter for an earlier stage does not contain later verification.

Evidence: [direct verifier invocation](https://github.com/salasya2/TraceFix/blob/e42df1bce51e499c6ad59089811e5cbd819c1677/services/orchestrator/src/tracefix/orchestrator/runner.py#L279-L285), [host environment and subprocess](https://github.com/salasya2/TraceFix/blob/e42df1bce51e499c6ad59089811e5cbd819c1677/packages/verification/src/tracefix/verification/harness.py#L66-L89), [Docker host collection](https://github.com/salasya2/TraceFix/blob/e42df1bce51e499c6ad59089811e5cbd819c1677/services/executor/src/tracefix/executor/adapters/docker.py#L74-L80).

**Required fix:** route preparation, exploration, collection and final verification through the same enforced executor boundary, with broker-controlled job manifests and an allowlisted environment. Do not run repository code in the API, orchestrator or publisher process environment.

### 3. [P1] A failed process can receive a full verification badge

The verifier checks JUnit inventory but does not require a successful process exit or reject a timeout when deciding `verified` and `badge`.

**Reproduced with real execution:** a patch fixed the owned averaging fixture and registered a harmless exit handler that terminates the child process with code 7. Pytest wrote its passing XML before the exit handler ran. TraceFix returned:

```json
{"verified": true, "badge": "full", "candidate_exit_code": 7, "target_passed": true, "errors": []}
```

This probe did not mock the harness or fabricate an XML report.

Evidence: [verification decision](https://github.com/salasya2/TraceFix/blob/e42df1bce51e499c6ad59089811e5cbd819c1677/packages/verification/src/tracefix/verification/pipeline.py#L128-L150).

**Required fix:** require successful supervisor status, exit code zero, no timeout/cancellation, complete expected inventory, and valid evidence before granting verification. Add regression tests for post-report crashes, timeouts, empty or stale reports, and inconsistent results.

### 4. [P1] Publication does not commit the proposed patch

The publisher creates a branch at the original source SHA and opens a PR immediately. It never applies the diff, creates the repaired tree/commit, or advances the branch to that commit.

**Reproduced:** publication returned `mode=draft_pr`, PR number 1, while the branch still pointed to `original-sha`. The fixture recorded zero created blobs, trees or commits. The test fixture permits a PR without checking whether its branch contains changes; real GitHub may reject a no-change PR.

Evidence: [publication sequence](https://github.com/salasya2/TraceFix/blob/e42df1bce51e499c6ad59089811e5cbd819c1677/services/publisher/src/tracefix/publisher/service.py#L125-L138).

**Required fix:** create a commit containing the exact verified tree, verify its contents against the attested patch, and publish the correct target branch. Make integration tests inspect the resulting commit and diff, not merely the returned PR number.

### 5. [P1] The actual server and investigation path remain fixture-only

`serve` calls `demo.build_context()`. That function overwrites the database URL with SQLite, uses local artifacts and `FixtureGitHub`, and seeds demo users/repositories. The investigation runtime unconditionally selects `FixtureProvider`, whose answer comes from `EXPECTED.patch`. The real provider adapter is not selected by that path.

**Impact:** setting a real provider name, database URL or API key does not turn the demonstrated flow into live TraceFix. Live GitHub REST and credential-broker implementations are also incomplete.

Evidence: [context creation](https://github.com/salasya2/TraceFix/blob/e42df1bce51e499c6ad59089811e5cbd819c1677/src/tracefix/demo.py#L29-L44), [fixture provider selection](https://github.com/salasya2/TraceFix/blob/e42df1bce51e499c6ad59089811e5cbd819c1677/services/orchestrator/src/tracefix/orchestrator/runner.py#L210).

**Required fix:** separate demo and configured application factories. Wire provider, GitHub, storage, database and executor interfaces from validated settings; finish the required real methods. Prove one owned-repository failed-run journey without a fixture answer.

### 6. [P1] Webhooks have no active durable dispatcher; Temporal is not wired

The webhook persists an outbox event, but `dispatch_outbox` is called only by tests. There is no service call to start a Temporal workflow. The Temporal worker never binds its required runtime. Even the manually invoked local dispatcher commits `dispatched_at` before running the investigation, so a crash between those actions strands the event.

Evidence: [premature dispatch commit](https://github.com/salasya2/TraceFix/blob/e42df1bce51e499c6ad59089811e5cbd819c1677/services/orchestrator/src/tracefix/orchestrator/outbox.py#L66-L74), [worker entrypoint](https://github.com/salasya2/TraceFix/blob/e42df1bce51e499c6ad59089811e5cbd819c1677/services/orchestrator/src/tracefix/orchestrator/worker.py#L12-L23), [unbound activity failure](https://github.com/salasya2/TraceFix/blob/e42df1bce51e499c6ad59089811e5cbd819c1677/services/orchestrator/src/tracefix/orchestrator/workflow.py#L38-L40).

**Required fix:** implement the outbox service and stable workflow start/reconciliation, initialize the worker properly, and make stages resumable. Inject crashes between persistence and dispatch and after major stages; restart and verify one eventual outcome. The current recovery test performs one normal investigation, not a crash/retry sequence.

### 7. [P1] Publication admission receives hardcoded safety facts

The route passes literal `refs_unchanged=True` and `installation_active=True`. It supplies the current workflow fingerprint as both approved and current values, and uses the run's old policy version even after retrieving the newest policy document.

**Impact:** source movement, installation revocation, workflow changes and policy changes are not independently detected by the production-facing route. Unit tests of the policy predicate do not exercise these missing reads.

Evidence: [publication request construction](https://github.com/salasya2/TraceFix/blob/e42df1bce51e499c6ad59089811e5cbd819c1677/apps/api/src/tracefix/api/routes/candidates.py#L169-L177).

**Required fix:** persist approval-bound facts and refetch current facts through the authenticated integration. Reject stale evidence. Acquire a durable publication operation before external writes; the current publisher locks are process-local and reconstructed on each API request.

### 8. [P1] Production executor and infrastructure are unfinished

The gVisor adapter always raises, including when `runtime_available=True`. Terraform modules contain descriptive outputs, not infrastructure resources. Compose lacks the advertised web/worker services; its API binds loopback inside the container and ignores its Postgres/S3 settings. Helm inherits the image's demo command rather than starting the service. The image also lacks dependencies needed for the intended PostgreSQL/test runtime.

Evidence: [gVisor unconditional exception](https://github.com/salasya2/TraceFix/blob/e42df1bce51e499c6ad59089811e5cbd819c1677/services/executor/src/tracefix/executor/adapters/gvisor.py#L28-L35), [Terraform control-plane placeholder](https://github.com/salasya2/TraceFix/blob/e42df1bce51e499c6ad59089811e5cbd819c1677/infra/terraform/modules/control_plane/main.tf), [image installation/default command](https://github.com/salasya2/TraceFix/blob/e42df1bce51e499c6ad59089811e5cbd819c1677/deploy/local/Dockerfile#L11-L13).

**Required fix:** implement job scheduling, runtime enforcement, networking and lifecycle cleanup; make Compose operational as a complete integration environment; provide real infrastructure resources and service-specific deployment commands. Treat these as unimplemented, not merely untested because a Linux pool is absent.

## Other material gaps

- **Cancellation and tenant controls:** cancellation updates database state without terminating actual execution; adapter `terminate` methods are no-ops. An organization emergency stop changes the global broker stop flag, affecting other tenants. Disengaging it does not remove the tenant from its stop set. See [cancellation route](https://github.com/salasya2/TraceFix/blob/e42df1bce51e499c6ad59089811e5cbd819c1677/apps/api/src/tracefix/api/routes/repair_runs.py#L114-L136) and [organization stop](https://github.com/salasya2/TraceFix/blob/e42df1bce51e499c6ad59089811e5cbd819c1677/apps/api/src/tracefix/api/routes/ops.py#L33-L40).
- **Database migration and RLS:** the online migration uses a synchronous engine with an async dialect. The audit reproduced `MissingGreenlet`. RLS helper code exists, but tenant context is not set by API sessions; SQLite tests do not establish PostgreSQL role isolation. See [migration engine](https://github.com/salasya2/TraceFix/blob/e42df1bce51e499c6ad59089811e5cbd819c1677/migrations/env.py#L26-L31).
- **Source provenance:** webhook head, base and execution SHAs are assumed identical and checkout trust is hardcoded. The snapshot digest hashes a directory path, not source contents. The provenance helper is unused. PR merge revisions and custom checkouts therefore lack reliable binding.
- **Agent feedback loop:** agent test requests ignore candidate identity and run the original snapshot. The main runner creates one candidate and stops after failed verification; there is no operational bounded retry loop. Model-supplied test IDs are forwarded as pytest arguments without rejecting option flags.
- **Benchmark validity:** the evaluator reads `EXPECTED.patch` directly and never invokes the model. Its ten passing cases demonstrate verifier fixtures, not AI repair quality. `reproduced` is set to all eligible cases, and pass-at-one/within-three use the same supplied-answer calculation. See [evaluation path](https://github.com/salasya2/TraceFix/blob/e42df1bce51e499c6ad59089811e5cbd819c1677/evals/runner/run_eval.py#L25-L28). The benchmark document does disclose its fixture basis; do not turn those numbers into a model-performance claim.
- **Operations evidence:** the restore test copies literal `sqlite-bytes`, without restoring a database or invoking the recovery scripts. The crash test does not crash. Most metrics are declared but never updated; tracing and dashboard provisioning are incomplete. `verify-staging` substitutes local tests. See [restore test](https://github.com/salasya2/TraceFix/blob/e42df1bce51e499c6ad59089811e5cbd819c1677/tests/chaos/test_restore.py#L7-L17).
- **UI scope:** the UI compiles and displays run/diff data, but organization settings are explanatory text, repository policy editing is not implemented in the screen, and no browser E2E test establishes the complete user journey. The existing E2E test is an API/fixture test.

## Completion against the original phases

| Specification phase | Assessment |
|---|---|
| 0: Contracts and threat model | Substantial documentation and schemas; implementation does not enforce all contracts |
| 1: Reproducible verifier | Working fixture execution, with critical correctness and execution-boundary gaps |
| 2: Durable ingestion | Partial; outbox and workflow definitions are not an operational durable pipeline |
| 3: Constrained agent | Fixture path works; real provider selection and candidate feedback loop incomplete |
| 4: Maintainer product | Basic API/UI works; secure SSO, PostgreSQL isolation and configuration UX incomplete |
| 5: Hostile execution | Incomplete; production adapter is a stub and verification bypasses adapters |
| 6: Controlled publishing | Incomplete; returned fixture PR contains no repaired commit and current-state checks are missing |
| 7: Operations and quality | Scaffolding and local checks exist; deployment, recovery, live benchmark and production evidence incomplete |

A single completion percentage would hide these dependency blockers. The accurate description today is **an embedded TraceFix prototype with a simulated agent and real local pytest verification**, not a completed enterprise service.

## Recommended completion order

1. **Repair verification correctness and authentication.** Require valid process completion, remove production fixture login, and add regression tests for the reproduced failures.
2. **Enforce one executor boundary.** Remove every host-execution path for repository code; implement real cancellation and tenant-scoped stops.
3. **Separate demo from real application startup.** Honor configured adapters, finish GitHub/token methods, and select the real model provider without loading expected answers.
4. **Complete durable ingestion and recovery.** Implement a dispatcher and working Temporal bootstrap, stage-level recovery, deduplication and missed-event reconciliation.
5. **Commit and publish the exact verified patch.** Add current-state checks, durable operation claims, correct source/target refs, and tests inspecting actual commit contents.
6. **Finish database/deployment wiring.** Fix Alembic, exercise RLS with a non-owner application role, and run the complete stack in Compose before cloud deployment.
7. **Run a real held-out agent evaluation and operational drills.** Measure failures as well as successes, instrument real metrics, and demonstrate restore/cancellation/rollback.
8. **Update `PROGRESS.md` to match executable evidence.** Separate implemented, fixture-tested, integration-tested, and production-validated work.

## Reproduction artifacts

- [Existing-suite JUnit results](<C:/Users/saite/OneDrive/Documents/New project 2/tmp/tracefix-audit-20260908/audit-pytest-results.xml>)
- [Ruff findings](<C:/Users/saite/OneDrive/Documents/New project 2/tmp/tracefix-audit-20260908/audit-ruff-results.json>)
- [Additional probe results](<C:/Users/saite/OneDrive/Documents/New project 2/tmp/tracefix-audit-20260908/audit-completion-probes.json>)
- [Probe script](<C:/Users/saite/OneDrive/Documents/New project 2/tmp/tracefix-completion-probes.py>)
- [Original enterprise build specification](<C:/Users/saite/OneDrive/Documents/New project 2/output/TraceFix-Enterprise-Build-Specification.md>)

The probes operate only on owned local fixtures and isolated database state. Publication uses in-memory GitHub, and authentication uses an in-process HTTP transport; no real PR, account session, or external model request was created.
