# Implementation Plan: Foundry-v2

**Branch**: `main` (existing checkout; no branch creation hook configured) | **Date**: 2026-10-10 | **Spec**: [DRAFT v0.2.0](spec.md)

## Summary

Build one authenticated Orchestrator web service, one SQLite-owning substrate service, and eight distinct core role workflows. Kubernetes runs evaluation workers in a dedicated namespace on the existing shared cluster. Cilium-enforced policies restrict external destinations to operator-maintained IP/CIDR and port/protocol entries. Native Ollama on the separate private GPU server serves `qwen3-coder:30b`; GitHub Issues receives confirmed findings only. There is one active evaluation per installation, with concurrent workers inside it.

This is an implementation design, not deployed or tested application code. The upstream seed and constitution remain unchanged. [Research](research.md), [data model](data-model.md), [contracts](contracts/README.md), and [quickstart](quickstart.md) are the outputs of this planning phase. Tasks are generated separately.

## Technical Context

**Language/Version**: CPython 3.12 for services, native Ollama integration, and LangGraph workflows. Python and Go are target-analysis languages; no Go application service is required. Go source is parsed deterministically using the Go tree-sitter grammar.

**Primary Dependencies**: FastAPI 0.143.0, Uvicorn 0.54.0, Pydantic 2.14.0, LangGraph 1.2.14, Ollama Python SDK 0.6.3, HTTPX 0.28.1, PyYAML 6.0.3, tree-sitter 0.26.0, tree-sitter-python 0.25.0, tree-sitter-go 0.25.0, cvss 3.6. CLI scanner pins: OSV-Scanner 2.6.0, Gitleaks 8.30.1. These are verified metadata pins, not a tested lockfile; implementation must resolve a transitive lock on Python 3.12 and run compatibility smoke tests before adopting it. LangGraph checkpoint transport is custom; no SQLite library runs in workers. Native Ollama SDK avoids a second model abstraction.

**Storage**: Standard-library SQLite, one owning process, WAL, foreign keys, `synchronous=FULL`, short serialized write transactions. CSI block-backed persistent volume with `ReadWriteOncePod`; no NFS/RWX database file. Artifacts and checkpoint blobs are stored through the same owner on its persistent volume, content-addressed, with transactional metadata visibility. Agent scratch space is disposable.

**Testing**: pytest 9.1.1; unit fixtures, API/schema contracts, SQLite concurrency/fault injection, deterministic Python/Go parser fixtures, mocked provider/GitHub adapters, and isolated Kubernetes integration tests. Live-model tests are separate from structural tests. Validate each obligation in [acceptance coverage](acceptance-coverage.md).

**Target Platform**: Linux workloads on existing Kubernetes >=1.30 with enforced Cilium NetworkPolicy support and CSI RWOP support. Installed server/Cilium/CSI versions are operator deployment inputs and checked rather than upgraded by this project. Windows is supported for editing/CLI client usage, not the production worker runtime.

**Project Type**: Python package with three process entrypoints: orchestrator, substrate, worker; server-rendered browser UI with a small same-origin JavaScript controller and event streaming. No separate frontend framework/build service.

**Performance Goals**: Structural status/start/stop operations do not await an LLM; heartbeat and lifecycle lanes continue during parsing and inference. Reclamation and hard-cap reactions obey configured monitoring bounds. Accuracy meets SC-002's >=90% reviewed precision; SC-003 requires all exploited samples to reproduce. Indexing only reparses changed files. These are acceptance requirements, not benchmark results or throughput promises.

**Constraints**: All 149 FRs and 9 NFRs remain in scope. Read-only source/config/prompts/policy mounts, no agent Kubernetes API credentials, one active evaluation, one database owner, no static guessed provider-rate ceiling. Operator config supplies positive inferred token rates when yield auto-stop is enabled; unknown usage suspends spend-derived completion. No vector search, extension roles, extra publication trackers, or compliance mapping.

**Scale/Scope**: One installation, one active evaluation containing one or more scoped Python/Go targets; per-role worker counts chosen by the operator. Substrate capacity is the first-build limit; do not silently migrate to distributed SQLite or PostgreSQL. [Deployment preflight](contracts/runtime.md) makes cluster-specific prerequisites explicit.

## Constitution Check

Pre-research gate: PASS against unchanged constitution v0.2.0 and the spec's [coverage review](constitution-review.md). Post-design gate: PASS by design obligations below; deployment and implementation checks are still required.

| Principle | Design enforcement | Required proof |
|---|---|---|
| I. Evidence | Mechanical citation resolution plus triage reasoning; structural evidence stored before verdict promotion | Invalid citations never publish |
| II. Surviving findings only | Reporter consumes confirmed-publication outbox; candidates and needs-review stay internal | Fixture for every verdict |
| III. Heartbeat liveness | Owner-clock heartbeats, independent sender lane, stale reaper; session limits never revoke healthy claims | Slow provider + kill-worker tests |
| IV. Atomic mortal claims | SQLite immediate transaction, claim generation and session identity fence, heartbeat-based release | Races and late-result rejection |
| V. Provider rate arbiter | Shared provider backpressure state for 429/503, adaptive retry; role composition is not provider throttling | Backpressure injection without fixed inference semaphore |
| VI. Coverage before yield | Atomic completion predicate includes full window, minimum runtime, coverage revision, complete accounting | Low yield with open coverage does not stop |
| VII. Demonstrated impact | Fresh Validator reproduction session receives only artifact and claim, no author's conversation | Partial impact and no-testbed remain not-exploited |
| VIII. Stable fingerprint | Target identity scope + normalized path/symbol/weakness tuple; line/snippet excluded | Shifted-line rerun updates same issue |
| IX. Infrastructure sandbox | Effective Cilium controls, read-only mounts, denied host privileges/API escalation, preflight | Container-root boundary probe |
| X. Operator authority | Authenticated control plane; agent advice has distinct origin; notes never close coverage | Prompt-injection and override audit |
| XI. Atomic persistence | SQLite transactions, immutable blob generation before metadata commit | Crash readers observe old or new complete generation |

No constitutional exception is requested. Original seed IDs remain interpreted using [ID concordance](requirement-id-map.md).

## Project Structure

### Documentation (this feature)

`specs/001-foundry/`: spec.md, plan.md, research.md, data-model.md, quickstart.md, acceptance-coverage.md, constitution-review.md, requirement-id-map.md, checklists/requirements.md, checklists/plan.md, and contracts/. `tasks.md` is produced by speckit-tasks, not this phase.

### Source Code (planned; not yet implemented)

```text
pyproject.toml
src/foundry_v2/
  api/                 # operator endpoints, auth, UI, streaming
  orchestrator/        # isolated lifecycle and conversational lanes
  substrate/           # SQLite owner, migrations, fenced API, blob store
  workers/             # worker lifecycle and independent heartbeat sender
  roles/               # eight distinct role graphs; no extensions
  checkpoints/         # HTTP-backed LangGraph checkpoint adapter
  indexing/            # deterministic Python/Go inventory and call graph
  integrations/        # native Ollama, GitHub, CodeGuard, scanner adapters
  governance/          # evidence, scope, budget, coverage and publication gates
  static/              # same-origin UI controller
  templates/           # dashboard and report templates
deploy/base/           # namespace, services, RBAC, workload/policy contracts
deploy/overlays/       # operator-supplied image/storage/CIDR/endpoint settings
tests/unit/
tests/contract/
tests/integration/
tests/acceptance/
tests/fixtures/        # Python/Go vulnerabilities, clean cases, mock adapters
```

**Structure Decision**: One Python package keeps shared DTOs and gates consistent, while separate processes isolate deterministic supervision, model work, and database ownership. No shared database mount is exposed to worker pods.

## Phase 0: Research Decisions

Resolved in [research.md](research.md): native Ollama and immutable model digest provenance; LangGraph remote checkpoint adapter; local SQLite ownership and fail-closed fencing; deterministic multi-language indexing; scanner integrations; GitHub ambiguous-publication reconciliation; operator authentication; namespace policy and local-inference accounting. No unresolved design marker remains. Actual deployment addresses, credentials, CIDRs, rates, identity groups and storage class are required environment inputs, not guessed facts.

## Phase 1: Design

### Process and role boundaries

The Orchestrator starts one Indexer, then reconciles requested core-role counts after index readiness. Workers are Kubernetes Jobs with immutable session IDs, not autonomous Deployments that respawn agents behind the Orchestrator. Only the lifecycle controller creates/terminates them. Kubernetes can restart the control services; agent Jobs use `restartPolicy: Never`, `backoffLimit: 0`; Orchestrator implements recorded crash backoff. Reconciliation adopts already-created jobs by persisted session labels after a supervisor crash.

The Orchestrator lifecycle container holds control-plane credentials; its model-backed conversational sidecar has separate mount and PID namespaces, no Kubernetes/API secrets, and only read/query/task/steer capabilities through a restricted internal bridge. Both implement the same Orchestrator role. Lifecycle, heartbeat sender and query work run in distinct processes/lanes; CPU-bound indexing is a separate worker process. Cartography has focused document passes and no startup gate. Triage's graph enforces its checklist; validation uses a fresh reproduction graph; detection consumes verbatim pinned CodeGuard prompt rules and structured caller/callee context. OSV/Gitleaks produce candidates that still require triage gates. No scanner result directly creates an issue.

### Substrate, heartbeats and claims

All mutations use scoped bearer credentials and idempotency keys. Claims have monotonic generations; updates require current holder and generation. Heartbeat timestamps come from substrate receipt, not agent clocks. The reaper uses only persisted stale heartbeats. Network partitions fence old writes; unknown owner state prevents fresh claims or completion. After a substrate restart, a monitoring grace equal to the configured stale interval allows restored workers to heartbeat before reaping; liveness never derives from workload runtime. Persisted restart epochs reject stale owner requests.

Single-owner Deployment uses `replicas: 1`, `Recreate`, RWOP volume and an exclusive process lock held for its lifetime; replacement remains unavailable until the previous owner is fenced/detached. Never force-remove an owner pod/volume attachment during uncertain node failure. Preflight rejects unreliable locking or missing RWOP; recovery is operator-observed and prioritizes integrity over availability.

### Publishing and external side effects

Only the Reporter requests publication, and one substrate-backed publisher identity serializes each fingerprint's durable outbox. Issue bodies carry a stable opaque publication marker scoped to target identity and fingerprint. On lost create responses, list all open/closed repository issues with pagination and inspect that marker; do not rely on indexed search. If creation outcome is ambiguous and no issue is visible yet, persist `uncertain`, retry read-only reconciliation, and require operator resolution rather than submit another create. GitHub does not provide a transaction with local SQLite: duplicate prevention is fail-closed and may sacrifice automatic availability. Updating labels/body is idempotent and nonconfirmed revisions withdraw previous confirmation.

### Provider and accounting

Native `/api/chat` requests include configured system prompt, tool schemas and model tag. Final `prompt_eval_count` and `eval_count` feed one ledger entry per call ID; record actual model digest at preflight. Shared 429/503 backoff respects provider retry information. Transport timeouts record unknown usage and disable spend-derived completion until reconciliation. Never infer zero monetary cost from self-hosting. Record operator-estimated rates, precision of totals and configured weights; no-model deterministic tests use response fixtures.

### Operator and agent identities

Serve UI/API over the cluster's existing TLS ingress. Verify operator bearer Kubernetes tokens through TokenReview and configured allowed user/group identities; reject service-account identities unless explicitly operator-authorized. Browser keeps a short-lived token in memory, sends Authorization headers, and never embeds it in URLs or local storage. No cookie authentication is used, so mutations cannot be authenticated by ambient cookies; enforce same-origin CORS and render source/report content escaped. Access groups and ingress hostname/certificate are deployer inputs. Orchestrator has narrowly scoped TokenReview and worker-Job permissions; workers have neither. Substrate tokens are installation-generated, role/evaluation/session scoped, stored as hashes and rotated on session changes. External GitHub token is mounted only in the publisher integration process; target/testbed secrets are disclosed only to authorized role tools and redacted in durable transcripts.

### UI and recovery

Dashboard/status share a substrate snapshot ID. GET status never invokes Ollama. Events expose monotonic sequence IDs and reconnect cursors; a retention gap forces snapshot refresh. Provider failures, incomplete index, unknown spend, stale sessions, uncertain publication and policy failure are prominent degraded states. Stops and budget changes remain operable while conversational requests wait. Configuration revisions are validated atomically; tightening rules immediately disables new disallowed tool actions and schedules controlled policy reconciliation. CIDR or endpoint expansion requires operator action and runtime preflight; no DNS-driven widening.

## Phase 2: Delivery and Validation Strategy

Implement the substrate/identity/transaction gates first, then supervision and runtime enforcement, deterministic indexing, role graphs, evidence/validation gates, reporting, and UI. This is phase sequencing, not the task backlog. Use [acceptance-coverage.md](acceptance-coverage.md) as the 149-FR coverage inventory and [quickstart.md](quickstart.md) for end-to-end validation.

Before production: resolve pinned dependencies on CPython 3.12; prove SQLite locking/volume fencing and backup restore; prove denied egress/write/API paths including root probe; prove model compatibility and quality separately; simulate every crash boundary; confirm one issue after a lost response; replay stopped and unchanged targets; verify all SC-001–SC-009. Record unavailable cluster/GPU checks as unexecuted, not passes.

## Complexity Tracking

No principle violations. Two control services and the remote checkpoint adapter are justified by the adopted single-owner SQLite constraint plus independently scheduled agent processes. Direct RWX SQLite access is rejected because it cannot establish the required locking and ownership guarantees. Alternative production providers, extra databases and frontend frameworks are excluded.
