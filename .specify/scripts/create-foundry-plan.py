"""Materialize the reviewed Foundry-v2 planning artifacts; no deployment."""
from pathlib import Path
import json

root = Path(__file__).resolve().parents[2]
f = root / 'specs/001-foundry'
def write(name, text):
    p = f / name
    p.parent.mkdir(parents=True, exist_ok=True)
    t = p.with_suffix(p.suffix + '.tmp')
    t.write_text(text.strip() + '\n', encoding='utf-8', newline='\n')
    t.replace(p)

write('plan.md', '''
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
''')

write('research.md', '''
# Research Decisions: Foundry-v2

Date: 2026-10-10. Primary official documentation and registry metadata informed these choices. Source verification is not live deployment validation. The user-selected stack is fixed; alternatives below explain design tradeoffs, not requests to revisit those choices.

## Native Ollama and model compatibility

**Decision:** Native Ollama Python SDK 0.6.3, exact `qwen3-coder:30b` tag, model digest recorded at startup. Gate startup on representative system/tool/token tests. Keep private HTTP without API authentication per operator choice.
**Rationale:** `/api/chat` supports tools and reports final inference token counts; the official tag advertises tool capability, but the deployed server/model must be checked. Backpressure includes 503 overload as well as 429. Interrupted calls have unknown usage rather than assumed zero.
**Alternatives:** OpenAI-compatible interface and ChatOllama were unnecessary given the explicit native-API choice.
**Sources:** [Chat API](https://docs.ollama.com/api/chat), [model tag](https://ollama.com/library/qwen3-coder:30b), [Ollama FAQ](https://docs.ollama.com/faq), [SDK metadata](https://pypi.org/pypi/ollama/0.6.3/json).

## Stateful LangGraph without shared database files

**Decision:** LangGraph 1.2.14 with an HTTP-backed `BaseCheckpointSaver` implemented over substrate transactions. Implement asynchronous get/list/put/put_writes/delete-thread contracts, namespace/thread isolation, version metadata, parent links and pending-write idempotency. Serializers must reject unsafe executable deserialization and preserve supported typed values using a controlled codec. Each Validator reproduction has a new thread and no author conversation.
**Rationale:** Checkpoints and pending writes preserve stage progress; the built-in SQLite saver in each worker would violate single ownership. Graph interrupts supply safe workflow boundaries; immediate operator interruption also needs worker cancellation and durable handoff, not just `interrupt()`.
**Alternatives:** Local checkpoint databases and a hosted LangGraph service add divergent state ownership or deployment dependencies.
**Sources:** [Checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers), [persistence](https://docs.langchain.com/oss/python/langgraph/persistence), [interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts), [LangGraph metadata](https://pypi.org/pypi/langgraph/1.2.14/json).

## SQLite ownership, transactions and persistence

**Decision:** One owning service/process, WAL on block-backed durable local filesystem, FULL sync, foreign keys, short `BEGIN IMMEDIATE` transactions. A Recreate single-replica workload with CSI RWOP plus lifetime process lock fences ownership. Immutable blobs become visible only after metadata commit; startup collects unreferenced completed/staging blobs conservatively. Back up using SQLite's supported backup mechanism and an artifact manifest, not copying a live main database while ignoring its WAL.
**Rationale:** SQLite's official guidance recommends keeping the database engine next to its files and serving remote clients through a proxy. RWO is not single-pod exclusion; RWOP provides that constraint for supported CSI storage. Fencing uncertain owners matters more than replacing them quickly.
**Alternatives:** RWX/NFS direct worker access is rejected; PostgreSQL would contradict the adopted datastore.
**Sources:** [SQLite over networks](https://www.sqlite.org/useovernet.html), [transactions](https://www.sqlite.org/lang_transaction.html), [WAL](https://www.sqlite.org/wal.html), [backup](https://www.sqlite.org/backup.html), [Kubernetes RWOP](https://kubernetes.io/docs/tasks/administer-cluster/change-pv-access-mode-readwriteoncepod/).

## Kubernetes and Cilium enforcement

**Decision:** Kubernetes >=1.30 prerequisites; dedicated evaluation namespace; Cilium-enforced NetworkPolicies with default deny, external `ipBlock` rules and ports, separate internal endpoint selectors and restricted DNS resolver access. Admission/RBAC disallow worker host networking, privileged mode, hostPath, policy edits and service-account escalation. Only operator-controlled installation provisions namespace policies. Verify additive inherited policies cannot widen the effective allowlist.
**Rationale:** Cilium CIDR rules do not substitute for selectors of Cilium-managed/internal endpoints. Standard NetworkPolicy permissions are additive; a namespace label alone establishes no boundary. Worker service accounts have `automountServiceAccountToken: false`; no cluster API credentials are available inside model tools.
**Alternatives:** FQDN rules were explicitly rejected by the user; automatic domain/IP expansion is excluded.
**Sources:** [Cilium L3 policy](https://docs.cilium.io/en/stable/security/policy/layer3/), [NetworkPolicy semantics](https://kubernetes.io/docs/concepts/services-networking/network-policies/), [Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/).

## Operator authentication and workload identities

**Decision:** TLS ingress, Kubernetes TokenReview plus configured operator user/group allowlist. Separate role/evaluation-scoped substrate credentials. Root sandbox probes are operator-run, nonprivileged with all escape capabilities dropped; admission exception for UID 0 is temporary and narrowly scoped to the probe, not granted to production workers.
**Rationale:** Port-forward/private Service transport alone does not authenticate every application request. Short-lived cluster identity avoids adding a new identity provider; shared cluster's actual identities are deployment parameters. Agent tokens cannot access operator control paths.
**Alternatives:** An identity gateway can replace TokenReview behind the same operator identity contract later, but no gateway product or OIDC provider is assumed in this build.
**Sources:** [Kubernetes authentication](https://kubernetes.io/docs/reference/access-authn-authz/authentication/), [authorization](https://kubernetes.io/docs/reference/access-authn-authz/authorization/).

## Deterministic Python/Go indexing and scanners

**Decision:** Tree-sitter 0.26.0 plus Python/Go grammars 0.25.0, deterministic symbol inventories and resolvable direct-call edges. Mark dynamic/unresolved calls explicitly; do not fabricate edges. Changed-file hashes and revision-pinned generations support incrementality. OSV-Scanner 2.6.0 handles supported lockfiles using an operator-staged vulnerability snapshot rather than implicit network access or executing target installers; unsupported dependency manifests create visible coverage gaps. Gitleaks 8.30.1 scans a scoped read-only source snapshot; redact credential values before candidate persistence.
**Rationale:** Required code structure cannot depend on LLM extraction. CodeGuard remains an LLM-evaluated pinned Markdown/prompt corpus, not a translated Semgrep rule library. Scanner coverage limitations must not be mistaken for a clean target.
**Alternatives:** Full language servers offer deeper semantics but add runtime/process complexity; they are not required for the minimum direct-static-call contract.
**Sources:** [tree-sitter Python API](https://github.com/tree-sitter/py-tree-sitter), [Python grammar](https://github.com/tree-sitter/tree-sitter-python), [Go grammar](https://github.com/tree-sitter/tree-sitter-go), [OSV release](https://github.com/google/osv-scanner/releases/tag/v2.6.0), [Gitleaks release](https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1), [CodeGuard](https://github.com/cosai-oasis/project-codeguard).

## Publication and scoring

**Decision:** One durable publisher outbox per target fingerprint, stable hidden publication marker, paginated open/closed issue reconciliation, uncertain outcomes pause creates. Score CVSS 4.0 using a pinned validator/calculator and official conformance vectors; derive label tiers from the score. No operator message channel is used for finding narration.
**Rationale:** GitHub create-issue offers no shared transaction with SQLite; blind POST retries can duplicate reports. Exactly one issue is achieved by refusing ambiguous retries until reconciliation resolves them, not by claiming an unavailable upstream idempotency key. Published markers use opaque target IDs and reveal no internal hostname/model/session.
**Alternatives:** Eventual search-index lookups and optimistic duplicate cleanup would violate the first-build single-issue requirement.
**Sources:** [GitHub issues](https://docs.github.com/en/rest/issues/issues), [GitHub REST practices](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api), [CVSS 4.0](https://www.first.org/cvss/v4.0/specification-document).

## Dependency and environment resolution

**Decision:** Pins in plan.md are exact package-release metadata choices. Create the resolved lockfile and container digest in implementation, using Python 3.12 compatibility resolution and tests; do not claim the list is already a compatible lock. Cluster versions, RWOP storage class, ingress identity groups, source/rule repositories, immutable revisions, approved CIDRs/ports, monetary rates, and GPU endpoint are deployer inputs validated against the configuration schema. GitHub API version is explicit adapter configuration tested against the selected supported version.
**Rationale:** Planning can select interfaces and versions without having access to the live cluster or private GPU host. Missing environment inputs must block deployment/preflight, not require guessing credentials or permission grants.
**Alternatives:** Unbounded dependencies or assumed storage/network access reduce repeatability and would hide deployment failures.
''')

write('data-model.md', '''
# Data Model: Foundry-v2

Date: 2026-10-10. SQLite owns durable metadata; agents never access its files. UTF-8 JSON payloads are schema-validated. IDs are opaque UUIDs; timestamps are owner-generated UTC instants. Every mutable aggregate has a monotonically increasing integer `version` and returns a conflict on stale expected versions. All foreign keys are enabled. Secrets and raw credentials are excluded from records and logs.

## Tables and validation

| Table | Primary key and core fields | Constraints / relationships |
|---|---|---|
| installations | installation_id, active_evaluation_id, owner_epoch | Single row per installation; active ownership acquired in immediate transaction |
| evaluations | evaluation_id, installation_id, state, config_revision, goals_revision, start/stop time, stop_reason, coverage_complete | One active evaluation; state transitions audited; completeness bound to goals revision |
| targets | target_id, vcs_url, repository_identity, pinned_commit, scope_json | Stable identity reused across reruns; multi-target evaluation join table prevents cross-target fingerprint collision |
| evaluation_targets | evaluation_id, target_id, commit, index_generation | Unique evaluation/target; exact revision scoped to run |
| config_revisions | revision_id, evaluation_id, validated_json, author_subject, created_at | Immutable; active revision changes atomically; references secret names only |
| sessions | session_id, evaluation_id, role, slot, incarnation, pod_name, state, heartbeat_at, restart_count | Unique active evaluation/role/slot; server receipt heartbeat, immutable incarnation |
| tasks | task_id, evaluation_id, target_id, role, title, description, priority, state, release_count | States open/blocked/closed; priority is not identity; CAS edits |
| claims | resource_type, resource_id, holder_session_id, generation, acquired_at | Composite PK resource; exclusive current holder; generation increments on each acquisition |
| findings | finding_id, target_id, fingerprint, path, symbol, weakness_key, version | Unique target_id/fingerprint; hash uses normalized POSIX-relative path + deterministic qualified symbol + stable vulnerability class, not lines/snippets/timestamps |
| finding_observations | evaluation_id, finding_id, candidate_technique, corpus_revision, verdict, evidence_id, validation_id, report_revision | One verdict per observation; candidate has null verdict; inheritance never treats prior TP as proof |
| evidence | evidence_id, observation_id, entry/trust/impact citations, citation_check, reasoning_blob | Citations identify evaluated commit/path/symbol/ranges; presence-is-vulnerability carve-out stored explicitly |
| validation_attempts | attempt_id, observation_id, author_session_id, reproduction_session_id, artifact_digest, result, observed_impact, explanation | Author and fresh reproducer differ; result success/failed/partial/no_testbed/prohibited; only success + observed headline impact can set exploited |
| reports | report_revision, observation_id, markdown_digest, cwe_id, cvss_vector, cvss_score, tier | Immutable revisions; score/vector validated; internal identities redacted |
| publications | publication_id, target_id, fingerprint, desired_report_revision, state, repo, issue_number, marker | Unique target/fingerprint; pending/creating/uncertain/published/updating/withdrawn/blocked; no blind create from uncertain |
| outbox | command_id, evaluation_id, kind, payload, state, last_error | Idempotent command ID; atomic commit with desired finding/report change |
| index_generations | generation_id, evaluation_id, target_id, commit, state, parent_generation | building/ready/failed; pointer switches only after complete required queries |
| code_units / call_edges | unit_id, generation_id, path, symbol, language, ranges, body_digest; caller_id/callee_id | Scope-enforced deterministic parse; edges distinguish static/unresolved; file hashes support changed-file reuse |
| security_documents | doc_id, evaluation_id, kind, generation, content_digest, fallback, source_revision | Immutable complete document, factual fallback flagged; each focused pass commits separately |
| coverage_items | item_id, evaluation_id, goals_revision, component, goal, attempt_bar, state, evidence_refs | Unique goal/component/revision; absent map does not authorize inventing goals; every closure has activity evidence |
| coverage_attempts | attempt_id, item_id, session_id, area, technique, result, evidence_refs | Append-only; attempts are advisory records, not global authority |
| model_calls | call_id, evaluation_id, session_id, model_tag, digest, state, prompt_tokens, output_tokens, rates, amount, usage_status | Reserved/completed/interrupted; unique call ID, one budget charge; known/estimated/unknown accounting status |
| provider_state | provider_id, blocked_until, reason, retry_observations, version | Shared adaptive 429/503 state; no fixed provider throughput guess |
| operator_messages | message_id, evaluation_id, session_id, kind, dedup_key, body, acknowledged_at | Equivalence policy uses normalized kind/resource/error key within configured dedup window; no candidate details |
| checkpoint_tuples | evaluation_id, thread_id, namespace, checkpoint_id, parent_id, metadata, channels_digest, version_map | Composite uniqueness; immutable checkpoint, API read/list; controlled typed serializer |
| checkpoint_writes | thread_id, namespace, checkpoint_id, task_id, write_index, channel, value_digest | Unique pending-write key ensures retry idempotency; transactionally related to checkpoint tuple |
| blobs | digest, byte_length, media_type, committed_at, ref_count | SHA-256 integrity; immutable writes staged/fsynced/renamed before DB commit; reads return only committed objects |
| audit_events | event_id, sequence, evaluation_id, actor_kind/id, action, resource, prior/new version, reason, timestamp | Append-only; monotonic sequence supports replay and UI snapshot cursor |
| idempotency_keys | actor_id, method, path, key, request_digest, response_digest/status | Unique request scope; same key/different payload is conflict; receipt commit and mutation atomic |
| credentials | credential_id, evaluation/session scope, role, token_hash, expires_at, revoked_at | No raw tokens persisted; worker secrets mounted outside model tool context; credentials never authenticate as operator |

## State machines

Evaluation: configured → preflight → indexing → running → draining → stopped; failure enters degraded/failed with reason. Degraded is an overlay that preserves underlying progress and prevents unsafe new operations. Resume creates a new run/session epoch under the same evaluation ledger; prior cap exhaustion blocks resume until its configured cap is raised. Completion only when goals-revision coverage, full positive spend window, minimum runtime, complete accounting, and low yield all agree in one transaction. Operator stop/override is separately audited.

Task: open → claimed (exclusive claim row) → closed, or release to open; N failed release cycles yield blocked. A stale session release increments fencing state. Reopen requires permitted operator/Coverage-Guide task edits; Coverage-Guide never closes its own directed work.

Finding: candidate → one triage verdict. A verified true-positive permits report publication; validation is independent and does not change truth on reproduction failure. No testbed gives no_testbed and not-exploited. Verdict revisions update the same observation/history; previously published nonconfirmed revisions withdraw the old confirmation. Manual overrides record actor/reason and preserve automated result provenance.

Publication: pending → creating → published; ambiguous transport response → uncertain → read-only reconciliation → published or operator-resolved pending. While uncertain no create retry is authorized. Update existing issue identity for revisions; if multiple historical matches are found, block for operator reconciliation without hiding duplicates.

## Transactions and crash boundaries

Claim operation executes `BEGIN IMMEDIATE`, checks active session heartbeat and role authorization, selects one eligible open resource, increments generation, and records holder atomically. Heartbeat and reaper share owner time; reaper releases only stale sessions. Every task/finding mutation asserts holder incarnation/generation and expected aggregate version in the same transaction. A returned stale result is 409 and cannot commit.

Persist completed artifacts to an immutable temporary file on the owner volume, flush/fsync, atomically rename by digest, then commit blob reference and aggregate pointer. Crashes before commit can leave an invisible orphan; they never erase the previous state. Checkpoint tuple, pending writes and stage completion use atomic owner transactions. Streaming logs are append-only committed chunks; snapshots include event sequence and ledger/coverage versions.

All write requests have an idempotency key. Backup uses an SQLite-consistent copy plus manifest of referenced blobs; restore verifies all digests and schema version before serving. Migration obtains exclusive owner lock and backs up first. Retention is operator-controlled; never delete active claims, required publication markers or audit provenance before the evaluation's declared retention boundary.
''')

write('contracts/README.md', '''
# Interface Contracts

- [openapi.json](openapi.json): operator and substrate HTTP endpoints, security and request/response envelopes. Prefixes are distinct authorization domains, even if development routes share a host.
- [config.schema.json](config.schema.json): strict deployment/evaluation YAML-as-JSON schema.
- [example-config.json](example-config.json): placeholder-only example; not deployable until operator values are supplied.
- [runtime.md](runtime.md): role permissions, checkpoint adapter, tool/provider contracts, Kubernetes constraints and recovery.

Contract version 0.1.0. Requests and DTOs are validated before executing side effects. Operator credentials never derive from target text; agent authentication cannot reach control endpoints. The service exposes OpenAPI-compatible schemas for contract tests; implementation-generated OpenAPI must be compared with this design before release. No endpoint here is currently implemented. JSON Schema validates shape; runtime.md specifies required semantic and authorization checks.
''')

write('contracts/runtime.md', '''
# Runtime and Integration Contracts

## Authorization matrix

| Actor | Permitted operations |
|---|---|
| Operator | Start/resume/drain/stop, configure, inspect all internal state, queue/prioritize work, steer, acknowledge messages, apply recorded overrides |
| Orchestrator lifecycle | Reconcile worker Jobs, active-evaluation lock, session registration, drain/cancellation, status and budgets; no autonomous verdict or exploited changes |
| Indexer | Scoped source reads, publish complete index generation and index queries |
| Cartographer | Source/index/goals reads, document-generation writes with factual fallback |
| Detector | Source/index/map/rule reads, candidate and attempted-area writes, queue leads; no GitHub writes |
| Triager | Claimed-candidate investigation, evidence and verdict writes, rule-gap records; no exploited flag |
| Validator | Claimed-TP authoring and independent fresh reproduction sessions, validation outcomes; no unobserved exploited flag |
| Coverage-Guide | Coverage evidence/closure under explicit bars, queue/update directed tasks, clear completeness on goal change; no closing its own work tasks |
| Reporter | Read confirmed reports/evidence, request publication/update/rollup; external token available only in dedicated integration process |
| Substrate infrastructure | Verify identities and transactions, heartbeat reaper, durable artifacts/checkpoints, idempotency and shared backpressure; cannot invent operator goals |

Authorization checks bind every worker request to installation/evaluation/role/session, independent of caller-supplied body fields. Reproduction sessions have no access to author conversation checkpoints. Allowed-role tools expose narrow operations; arbitrary shell is isolated inside sandbox and never inherits control-service credentials.

## Configuration semantic validation

Beyond JSON Schema: parse IP/CIDRs and URLs; enforce exact approved host IP/port mapping, private Ollama network placement, nonempty authorized operator subject/group policy, no placeholder or all-zero revision, storage/admission prerequisites, approved mount paths and secret references. Require stale_seconds > heartbeat_seconds, hard_session_seconds > soft_session_seconds, and backoff_max_seconds >= backoff_initial_seconds. Empty/template goals remain waiting rather than becoming invented goals. The example uses documentation IP ranges and illustrative tunable values, not production defaults. Its yield stopping is intentionally disabled until positive estimated rates are supplied.

## HTTP semantics

Operator bearer credentials are validated with TokenReview and configured subject/group policy. Agent bearer credentials are random, scoped, revocable tokens with stored hashes. Operator API is TLS-only at ingress; substrate uses internal TLS and per-workload tokens. Private Ollama HTTP is the explicit exception. All mutations require `Idempotency-Key`; CAS aggregate updates carry `expected_version`; claimed writes carry `claim_generation` and the session identity from authentication.

Errors: 400 malformed request; 401 missing/invalid credential; 403 forbidden role/scope; 404 scoped resource absent; 409 stale version/claim, mismatched idempotency key, active evaluation or uncertain ownership; 422 invalid configuration/capability; 503 degraded dependency. Error bodies include code, actionable message, request_id and safe details; never credentials. Read list responses use opaque cursor and stable ordering. SSE events use durable sequence IDs, event kind, role and snapshot ID; reconnect from Last-Event-ID or request a new snapshot if history was pruned. Progress messages cannot contain candidate details in operator notifications.

The session-registration endpoint is restricted to authenticated Orchestrator infrastructure credentials, not worker tokens. Generation/report writes, task edits, coverage closure and overrides obey the authorization matrix plus CAS/claim rules. Empty LangGraph checkpoint namespace is encoded as `_root` in path segments; other names are URL-encoded, and the saved namespace retains its original value. Opaque ID fields are always checked against authenticated evaluation scope.

## Checkpoint adapter

Implement LangGraph `BaseCheckpointSaver` async methods `aget_tuple`, `alist`, `aput`, `aput_writes`, `adelete_thread` and matching required versioning/serialization methods for the pinned release. All calls route through substrate, preserving thread_id/checkpoint_ns/checkpoint_id, parent metadata, typed channel values and pending-write uniqueness. Thread identity includes evaluation and role session; reproduction creates a fresh thread with permitted artifact/claim only. No pickle/unrestricted object loading from target-controlled content. Checkpoint conformance tests compare resume and pending-write behavior against an isolated reference saver used only in tests.

## Index and provider tools

Index query operations: list-functions, function-body, callers, callees, symbol lookup, full-text search. Queries identify evaluation, target, committed generation and scoped symbol/path. Dynamic unresolved calls are marked; parsing errors produce visible exclusions and cannot silently satisfy coverage. Source fetch/index input is pinned to full commit and scoped paths. Hash-based incrementality does not accept prompt-authored indexes as the sole inventory.

Ollama `/api/chat`: exact model tag, system message, allowed tool definitions, prior role conversation and structured output schema where required. Record tag and observed digest, final token counts and call IDs; streaming must retain the terminal accounting frame. Tool results are untrusted data. Shared adaptive 429/503 retries keep heartbeats alive. There is no static guessed inference semaphore; operator role slots define desired composition. OSV and Gitleaks scanner results are normalized candidates with evidence/provenance, never published verdicts.

GitHub: service-account token with source read, reporting issues read/write and labels; create/update reports and labels only through reporter publisher path. Commit-pinned links use encoded paths. The internal opaque publication marker contains no hostnames/model/session. Lost POST outcome remains uncertain until reconciled by paginated repository reads or operator action. Never issue a second POST on mere timeout.

## Kubernetes deployment contract

Existing cluster >=1.30, supported Cilium, CSI RWOP and block-backed storage with correct fsync/locking are preconditions. One substrate Deployment replica, Recreate update, RWOP PVC, lifetime file lock; no duplicate owner while fencing is uncertain. One Orchestrator replica reconciles persisted session Jobs. Its deterministic lifecycle container alone holds Kubernetes credentials; the conversational sidecar has no shared process namespace or credential mount and cannot invoke arbitrary controller actions from model content. Worker Jobs cannot be restarted by Kubernetes retry loops; lifecycle controller alone maintains configured counts. Database owner uses a distinct identity from agents.

Worker pods: read-only root/source/config/prompts/policy mounts; only dedicated scratch and artifact staging writable; unprivileged production UID; all capabilities dropped, no privilege escalation, no host namespace/network/hostPath, no service-account automount. Agent pod definitions are immutable operator templates. Admission rejects escalation even if a controller credential is misused. Installation identities manage namespace/RBAC/policy/PVC; Orchestrator can manage only allowed worker Jobs and cannot edit policies or grant RBAC. Allow no unconstrained interactive pod exec identity to model tools.

Default-deny egress/ingress applies to workers; external IP/CIDRs are paired with approved ports/protocols. Internal selectors permit only substrate and necessary control signals; DNS is allowed only to the cluster resolver. Cilium-managed pod/node destinations are not implicitly authorized by external CIDR entries. Check inherited clusterwide/additive policies and both IP families, metadata/node endpoints, and read-only writes. A nonprivileged root probe uses a narrowly operator-approved test pod exception, proves boundaries, then is deleted; it never relaxes worker admission. Testbeds are operator-provisioned/reset and must themselves have bounded pivot reachability.

Preflight blocks start on failed identity/policy/read-only/storage checks, missing YAML fields, unknown approved CIDRs, unreachable integrations or incompatible model. It does not create permissive fallback rules. Provide ingress hostname/cert, allowed operator identities, source/report/rule repositories and revisions, private Ollama base URL, storage class, network entries, token rates and runtime bounds at deployment. Cluster admission approvals are deployment prerequisites, not assumed acquired by this planning phase.
''')

write('quickstart.md', '''
# Quickstart Validation Guide: Foundry-v2

These commands describe the planned implementation. This repository currently contains specifications and planning artifacts only: package entrypoints, tests and deployment manifests below will be supplied by implementation. No live cluster, GPU or GitHub write was performed during planning.

## Prerequisites

CPython 3.12, Git, a supported container build tool, kubectl, existing Kubernetes >=1.30 with enforced Cilium and CSI RWOP, block-backed SQLite storage, TLS ingress, operator cluster identity, and authorized test fixtures. Private GPU host must serve `qwen3-coder:30b` via native Ollama HTTP. Operator supplies exact IP/CIDR+port entries, repositories/commit pins, CodeGuard corpus revision, identity groups and positive estimated token rates if yield stopping is enabled. Real GitHub/testbed credentials are Kubernetes Secrets, never committed files.

## Local structural validation (after implementation)

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes -r requirements.lock
python -m pip install --no-deps -e .
python -m pytest tests/unit tests/contract tests/integration -m 'not live_cluster and not live_model'
python -m foundry_v2.config validate --file operator-config.yaml
```

On Windows use `.venv\\Scripts\\Activate.ps1` and a Python 3.12 interpreter. The lockfile and package are implementation outputs. Expected: schemas and role authorization pass; all FR fixture obligations are collected; no real model or tracker is needed for deterministic structural tests. Invalid placeholder addresses, missing secrets, zero yield rates, unsafe mounts and unmatched CIDRs produce named errors before startup.

## Deployment preparation (operator-reviewed)

```sh
kubectl config current-context
kubectl kustomize deploy/overlays/operator > rendered-foundry.yaml
kubectl diff -f rendered-foundry.yaml
kubectl apply --dry-run=server -f rendered-foundry.yaml
```

Inspect namespace, external CIDRs/ports, internal selectors, RBAC, admission, RWOP storage and workload templates. Installation/apply and external publication require the user's deployment authorization at implementation time. Planning does not grant it. Supply secrets using the organization's secret management path; do not print their values or place bearer tokens in URLs. Confirm only the SQLite owner mounts its database and that replacement cannot overlap it.

## End-to-end validation (authorized test environment)

1. Run the implementation preflight command `python -m foundry_v2.cli preflight --config operator-config.yaml`. It verifies denied egress/write/API probes, operator identity, immutable source/corpus revisions, database fencing, GitHub permissions, private Ollama tool/system/token capabilities, and testbed inventory if present. Failure prevents evaluation startup.
2. Start through authenticated `POST /v1/evaluations`. Expect Indexer first, then seven other role types; pending Cartographer passes do not delay them. `GET /v1/evaluations/{id}/status` and dashboard snapshot IDs must match.
3. Use a Python/Go fixture target with known seeded security defects and clean cases. Verify rule/dependency/secret/exploratory candidates are internal until verified triage. Sample confirmed issues meet >=90% precision and include pinned citations, CWE, valid CVSS 4.0, and the fixed labels.
4. With an authorized disposable testbed, independently reproduce an exploited finding from its issue/artifact only. Without a testbed, verify no exploited flag, an unexecuted artifact and the no-testbed reason. PoC header includes Authorized testing only and setup prerequisites.
5. Kill one worker during a claim and delay a different worker's provider response while it heartbeats. Only the dead worker's claim expires within stale threshold plus one monitor cycle. Late old-generation writes return 409. Supervisor session rotation cannot revoke a healthy claim on the clock alone.
6. Race starts and claims; exactly one evaluation owns installation and no task has two holders. Crash the SQLite owner during a generation update: readers later see old or new complete state and committed progress survives replacement. Test volume/node fencing and consistent backup restore.
7. Simulate lost GitHub create response. One issue is recovered by opaque marker; uncertain create remains blocked rather than duplicating. Replay unchanged input and shift source lines: no duplicate findings/issues, only changed files parsed. Withdraw a changed nonconfirmed verdict on the original issue.
8. Lower yield with an open coverage item: fleet continues. Complete all operator goals, accumulate the positive configured spend window/minimum runtime, then lower yield: fleet drains. Unknown token accounting blocks spend-derived completion. Orchestrator keeps a monotonic local runtime watchdog so hard runtime caps remain effective during provider/substrate degradation; operator stop always works.
9. Inject provider 429/503, GitHub outage, partial map, malformed citations, prompt injection and policy failure. Check prominent degraded states, shared adaptive retry, no secret values in logs, no authority change and no automatic allowlist expansion.

## Completion evidence

Record SC-001–SC-009 results, FR fixture report, model digest/corpus revision, deployment policy probe output without credentials, sample report/PoC reproduction, stopped-evaluation ledger, and backup/restore hashes. [acceptance-coverage.md](acceptance-coverage.md) lists all 149 obligations. Live checks that cannot run are unexecuted, not passed. After tests, stop evaluation and operator-reset/delete disposable fixtures according to the inventory; retain required audit and publication provenance.
''')

# Machine-readable contracts are emitted separately below.
def obj(properties, required=None):
    return {'type':'object','additionalProperties':False,'properties':properties,'required':required if required is not None else list(properties)}
string={'type':'string','minLength':1}
integer={'type':'integer','minimum':0}
positive={'type':'number','exclusiveMinimum':0}
boolean={'type':'boolean'}
nullable_amount={'type':['number','null'],'exclusiveMinimum':0}
def array(items): return {'type':'array','items':items}
def enum(values): return {'type':'string','enum':values}
def ref(name): return {'$ref':'#/components/schemas/'+name}
role=enum(['orchestrator','indexer','cartographer','detector','triager','validator','reporter','coverage-guide'])
verdict=enum(['true-positive','false-positive','needs-review','not-applicable','code-quality'])
json_value={'type':'object','additionalProperties':True}
schemas={
 'Error':obj({'code':string,'message':string,'request_id':string,'details':json_value},['code','message','request_id']),
 'Receipt':obj({'request_id':string,'resource_id':string,'version':integer,'state':string},['request_id','resource_id','version']),
 'Snapshot':obj({'snapshot_id':integer,'evaluation_id':string,'state':string,'agents':array(json_value),'counts':json_value,'coverage':json_value,'budget':json_value,'degraded':array(string)}),
 'Page':obj({'items':array(json_value),'next_cursor':{'type':['string','null']},'snapshot_id':integer}),
 'StartEvaluation':obj({'configuration':json_value,'expected_installation_version':integer}),
 'Control':obj({'action':enum(['drain','stop','resume']),'reason':string,'expected_version':integer}),
 'ConfigUpdate':obj({'configuration':json_value,'expected_version':integer}),
 'OperatorQuery':obj({'question':string}),
 'TaskCreate':obj({'role':role,'target_id':string,'title':string,'description':string,'priority':integer},['role','title','description','priority']),
 'TaskUpdate':obj({'state':enum(['open','blocked','closed']),'description':string,'priority':integer,'expected_version':integer},['expected_version']),
 'Steer':obj({'session_id':string,'role':role,'message':string,'mode':enum(['idle','interrupt'])},['message','mode']),
 'Override':obj({'resource_type':enum(['finding','coverage','stop']),'resource_id':string,'decision':json_value,'reason':string,'expected_version':integer}),
 'Ack':obj({'expected_version':integer,'reply':string},['expected_version']),
 'Heartbeat':obj({'session_id':string,'incarnation':integer,'last_event_sequence':integer}),
 'ClaimRequest':obj({'resource_type':enum(['task','finding']),'role':role}),
 'Claim':obj({'resource_id':string,'resource_type':enum(['task','finding']),'session_id':string,'generation':integer,'owner_epoch':integer,'payload':json_value}),
 'ClaimWrite':obj({'claim_generation':integer,'expected_version':integer,'operation':enum(['complete','release','update']),'payload':json_value}),
 'Candidate':obj({'target_id':string,'path':string,'symbol':string,'weakness_key':string,'technique':enum(['rule','dependency','secret','exploratory']),'description':string,'source_revision':string,'corpus_revision':string},['target_id','path','symbol','weakness_key','technique','description','source_revision']),
 'VerdictWrite':obj({'claim_generation':integer,'expected_version':integer,'verdict':verdict,'evidence':json_value,'reasoning_digest':string}),
 'ValidationWrite':obj({'claim_generation':integer,'expected_version':integer,'artifact_digest':string,'result':enum(['success','failed','partial','no_testbed','prohibited']),'observed_impact':string,'reason':string,'author_session_id':string,'reproduction_session_id':string},['claim_generation','expected_version','result','reason','author_session_id','reproduction_session_id']),
 'GenerationWrite':obj({'kind':enum(['index','architecture','attack_surface','trust_boundaries','data_flow','auth_model','threat_model','coverage','notes']),'expected_version':integer,'content':json_value,'blob_digests':array(string)}),
 'IndexQuery':obj({'target_id':string,'generation_id':string,'operation':enum(['list-functions','function-body','callers','callees','find-symbol','full-text']),'arguments':json_value}),
 'CoverageWrite':obj({'goals_revision':integer,'expected_version':integer,'items':array(json_value),'complete':boolean}),
 'Message':obj({'kind':enum(['blocker','request','feedback','info']),'dedup_key':string,'body':string}),
 'ModelCall':obj({'call_id':string,'phase':enum(['reserve','complete','interrupted']),'model_tag':string,'model_digest':string,'prompt_tokens':integer,'output_tokens':integer,'usage_status':enum(['known','estimated','unknown'])},['call_id','phase','model_tag','usage_status']),
 'Backpressure':obj({'provider_id':string,'http_status':{'type':'integer','enum':[429,503]},'retry_after_seconds':positive},['provider_id','http_status']),
 'Publish':obj({'finding_id':string,'report_revision':integer,'expected_version':integer}),
 'Checkpoint':obj({'checkpoint_id':string,'parent_id':{'type':['string','null']},'channel_values':json_value,'channel_versions':json_value,'versions_seen':json_value,'metadata':json_value,'pending_writes':array(json_value),'codec_version':string}),
 'CheckpointWrites':obj({'task_id':string,'task_path':string,'writes':array(obj({'write_index':{'type':'integer'},'channel':string,'value':{}},['write_index','channel','value']))}),
 'SessionRegistration':obj({'session_id':string,'role':role,'slot':integer,'incarnation':integer,'pod_name':string}),
 'ReportWrite':obj({'claim_generation':integer,'expected_version':integer,'content_digest':string,'cwe_id':string,'cvss_vector':string,'cvss_score':{'type':'number','minimum':0,'maximum':10}}),
}
api={'openapi':'3.1.0','info':{'title':'Foundry-v2 operator and substrate API','version':'0.1.0','description':'Design contract. Not yet implemented. Every mutation is idempotent; role/session/claim authorization is enforced server-side.'},'servers':[{'url':'https://foundry.example.invalid'}],'paths':{},'components':{'schemas':schemas,'securitySchemes':{'OperatorBearer':{'type':'http','scheme':'bearer','bearerFormat':'Kubernetes operator token'},'AgentBearer':{'type':'http','scheme':'bearer','bearerFormat':'scoped session token'}}}}
def endpoint(path, method, ident, request=None, response='Receipt', security='AgentBearer', description='', code='200'):
    params=[{'name':n,'in':'path','required':True,'schema':string} for n in __import__('re').findall(r'\{([^}]+)\}',path)]
    if method not in ('get',):
        params.append({'name':'Idempotency-Key','in':'header','required':True,'schema':string})
    if method=='get' and response=='Page':
        params.extend([{'name':'cursor','in':'query','schema':string},{'name':'limit','in':'query','schema':{'type':'integer','minimum':1,'maximum':100}}])
    op={'operationId':ident,'description':description or ident,'security':[{security:[]}],'parameters':params,'responses':{code:{'description':'Success','content':{'application/json':{'schema':ref(response)}}},'default':{'description':'Actionable error; see runtime.md for status semantics','content':{'application/json':{'schema':ref('Error')}}}}}
    if request: op['requestBody']={'required':True,'content':{'application/json':{'schema':ref(request)}}}
    api['paths'].setdefault(path,{})[method]=op

o='/v1/evaluations'
endpoint(o,'post','startEvaluation','StartEvaluation',security='OperatorBearer',code='202',description='Validate full configuration schema; atomically reserve one active evaluation; preflight/indexing are asynchronous. Conflicting start returns 409.')
for path,method,ident,req,res in [
 ('/{evaluation_id}/status','get','getStatus',None,'Snapshot'),
 ('/{evaluation_id}/control','post','controlEvaluation','Control','Receipt'),
 ('/{evaluation_id}/configuration','put','updateConfiguration','ConfigUpdate','Receipt'),
 ('/{evaluation_id}/questions','post','askQuestion','OperatorQuery','Receipt'),
 ('/{evaluation_id}/tasks','post','queueTask','TaskCreate','Receipt'),
 ('/{evaluation_id}/tasks','get','listTasks',None,'Page'),
 ('/{evaluation_id}/tasks/{task_id}','patch','editTask','TaskUpdate','Receipt'),
 ('/{evaluation_id}/steering','post','steerWorker','Steer','Receipt'),
 ('/{evaluation_id}/overrides','post','recordOverride','Override','Receipt'),
 ('/{evaluation_id}/findings','get','listFindings',None,'Page'),
 ('/{evaluation_id}/messages/{message_id}/ack','post','ackMessage','Ack','Receipt')]:
    endpoint(o+path,method,ident,req,res,'OperatorBearer')
endpoint(o+'/{evaluation_id}/events','get','streamEvents',None,'Page','OperatorBearer',description='SSE stream; durable event id and Last-Event-ID reconnect; return 409 refresh_required on cursor retention gap.')
eventop=api['paths'][o+'/{evaluation_id}/events']['get']
eventop['parameters'].append({'name':'Last-Event-ID','in':'header','schema':string})
eventop['responses']['200']['content']={'text/event-stream':{'schema':{'type':'string'}}}

b='/substrate/v1/evaluations/{evaluation_id}'
routes=[
 ('/sessions','post','registerSession','SessionRegistration','Receipt'),
 ('/sessions/heartbeat','post','heartbeat','Heartbeat','Receipt'),
 ('/snapshot','get','readSubstrateSnapshot',None,'Snapshot'),
 ('/tasks','post','submitTask','TaskCreate','Receipt'),
 ('/tasks','get','readTasks',None,'Page'),
 ('/tasks/{task_id}','patch','updateTask','TaskUpdate','Receipt'),
 ('/claims','post','claimWork','ClaimRequest','Claim'),
 ('/claims/{resource_id}','patch','writeClaimedWork','ClaimWrite','Receipt'),
 ('/findings','post','submitCandidate','Candidate','Receipt'),
 ('/findings','get','readFindings',None,'Page'),
 ('/findings/{finding_id}/verdict','put','assignVerdict','VerdictWrite','Receipt'),
 ('/findings/{finding_id}/validation','post','recordValidation','ValidationWrite','Receipt'),
 ('/findings/{finding_id}/reports','post','commitReport','ReportWrite','Receipt'),
 ('/generations','get','readGenerations',None,'Page'),
 ('/generations','post','commitGeneration','GenerationWrite','Receipt'),
 ('/index/query','post','queryIndex','IndexQuery','Page'),
 ('/coverage','put','writeCoverage','CoverageWrite','Receipt'),
 ('/messages','post','postMessage','Message','Receipt'),
 ('/model-calls','post','recordModelCall','ModelCall','Receipt'),
 ('/provider-backpressure','post','observeBackpressure','Backpressure','Receipt'),
 ('/publication-intents','post','requestPublication','Publish','Receipt'),
 ('/checkpoints/{thread_id}/{namespace}','get','listCheckpoints',None,'Page'),
 ('/checkpoints/{thread_id}/{namespace}/{checkpoint_id}','get','getCheckpoint',None,'Checkpoint'),
 ('/checkpoints/{thread_id}/{namespace}/{checkpoint_id}','put','putCheckpoint','Checkpoint','Receipt'),
 ('/checkpoints/{thread_id}/{namespace}/{checkpoint_id}/writes','put','putCheckpointWrites','CheckpointWrites','Receipt'),
 ('/checkpoints/{thread_id}/{namespace}','delete','deleteCheckpointThread',None,'Receipt'),
]
for path,method,ident,req,res in routes: endpoint(b+path,method,ident,req,res)
api['paths'][b+'/claims']['post']['responses']['204']={'description':'No eligible work; no claim acquired'}
endpoint(b+'/blobs/{digest}','put','writeBlob',None,'Receipt',description='Immutable content-addressed upload; digest is verified. Only committed metadata makes blob visible.')
api['paths'][b+'/blobs/{digest}']['put']['requestBody']={'required':True,'content':{'application/octet-stream':{'schema':{'type':'string','format':'binary'}}}}
endpoint(b+'/blobs/{digest}','get','readBlob',None,'Receipt')
api['paths'][b+'/blobs/{digest}']['get']['responses']['200']['content']={'application/octet-stream':{'schema':{'type':'string','format':'binary'}}}
write('contracts/openapi.json',json.dumps(api,indent=2))

role_counts=obj({r:{'type':'integer','minimum':1 if r=='indexer' else 0} for r in ['indexer','cartographer','detector','triager','validator','reporter','coverage-guide']})
target=obj({'repository':string,'revision':{'type':'string','pattern':'^[0-9a-f]{40}$'},'include':array(string),'exclude':array(string)})
net=obj({'cidr':string,'ports':array(obj({'port':{'type':'integer','minimum':1,'maximum':65535},'protocol':enum(['TCP','UDP'])}))})
config=obj({
 'schema_version':{'const':'0.1.0'},
 'name':string,
 'target':{'type':'array','minItems':1,'items':target},
 'goals':{'type':'string'},
 'testbed':{'oneOf':[{'type':'null'},obj({'endpoints':array(obj({'url':string,'scope':string,'credential_ref':{'type':['string','null']}})),'reset':string,'operator_contact':string,'prohibited_actions':array(string)})]},
 'rules':obj({'hard_rules':array(string)}),
 'detection':obj({'corpus_repository':string,'corpus_revision':{'type':'string','pattern':'^[0-9a-f]{40}$'},'osv_database_ref':string,'techniques':{'const':['rule','dependency','secret','exploratory']}}),
 'fleet':obj({'counts':role_counts,'soft_session_seconds':positive,'hard_session_seconds':positive,'validator_attempts':{'type':'integer','minimum':1},'heartbeat_seconds':positive,'stale_seconds':positive,'monitor_seconds':positive,'drain_seconds':positive,'block_after_releases':{'type':'integer','minimum':1},'backoff_initial_seconds':positive,'backoff_max_seconds':positive,'notes_max_bytes':{'type':'integer','minimum':1},'message_dedup_seconds':positive}),
 'sandbox':obj({'namespace':string,'storage_class':string,'external_allowlist':array(net),'read_only_paths':array(string),'writable_paths':array(string)}),
 'budget':obj({'spend_cap':nullable_amount,'runtime_cap_seconds':nullable_amount,'currency':string,'input_per_million':{'type':'number','minimum':0},'output_per_million':{'type':'number','minimum':0},'yield_enabled':boolean,'yield_window_spend':positive,'yield_min_runtime_seconds':positive,'yield_threshold':{'type':'number','minimum':0},'severity_weights':obj({k:{'type':'number','minimum':0} for k in ['none','low','medium','high','critical']}),'exploited_multiplier':positive}),
 'integrations':obj({'ollama':obj({'base_url':{'type':'string','pattern':'^http://'},'model':{'const':'qwen3-coder:30b'}}),'github':obj({'source_token_ref':string,'report_repository':string,'api_version':string}),'operator_auth':obj({'allowed_subjects':array(string),'allowed_groups':array(string),'ingress_host':string,'tls_secret_ref':string})}),
})
config['$schema']='https://json-schema.org/draft/2020-12/schema'
config['$id']='https://foundry.example.invalid/contracts/config.schema.json'
config['allOf']=[{'if':{'properties':{'budget':{'properties':{'yield_enabled':{'const':True}},'required':['yield_enabled']}},'required':['budget']},'then':{'properties':{'budget':{'properties':{'input_per_million':positive,'output_per_million':positive}}}}}]
write('contracts/config.schema.json',json.dumps(config,indent=2))
example={
 'schema_version':'0.1.0','name':'authorized-fixture-evaluation',
 'target':[{'repository':'https://github.com/REPLACE_OWNER/REPLACE_TARGET','revision':'0'*40,'include':['**/*.py','**/*.go'],'exclude':['vendor/**','generated/**']}],
 'goals':'Evaluate authentication, authorization, input handling, dependencies, and exposed secrets in the authorized fixture target.',
 'testbed':None,'rules':{'hard_rules':['No denial of service, data deletion, credential changes, or actions affecting non-test users.']},
 'detection':{'corpus_repository':'https://github.com/cosai-oasis/project-codeguard','corpus_revision':'5bfe8f937bf0a60bc567403a09280412007bc9cc','osv_database_ref':'operator-staged-osv-fixture-snapshot','techniques':['rule','dependency','secret','exploratory']},
 'fleet':{'counts':{r:1 for r in role_counts['properties']},'soft_session_seconds':9000,'hard_session_seconds':9900,'validator_attempts':3,'heartbeat_seconds':10,'stale_seconds':60,'monitor_seconds':5,'drain_seconds':120,'block_after_releases':3,'backoff_initial_seconds':1,'backoff_max_seconds':1800,'notes_max_bytes':32768,'message_dedup_seconds':300},
 'sandbox':{'namespace':'foundry-v2-evaluation','storage_class':'REPLACE_RWOP_BLOCK_STORAGE_CLASS','external_allowlist':[{'cidr':'192.0.2.10/32','ports':[{'port':11434,'protocol':'TCP'}]},{'cidr':'198.51.100.0/24','ports':[{'port':443,'protocol':'TCP'}]}],'read_only_paths':['/target','/config','/prompts','/policy'],'writable_paths':['/scratch','/artifacts']},
 'budget':{'spend_cap':None,'runtime_cap_seconds':3600,'currency':'USD','input_per_million':0,'output_per_million':0,'yield_enabled':False,'yield_window_spend':1,'yield_min_runtime_seconds':600,'yield_threshold':0,'severity_weights':{'none':0,'low':1,'medium':3.15,'high':9.9225,'critical':31.255875},'exploited_multiplier':2},
 'integrations':{'ollama':{'base_url':'http://192.0.2.10:11434','model':'qwen3-coder:30b'},'github':{'source_token_ref':'k8s-secret:github-service-account/token','report_repository':'REPLACE_OWNER/REPLACE_REPORTS','api_version':'2026-03-10'},'operator_auth':{'allowed_subjects':['REPLACE_OPERATOR_SUBJECT'],'allowed_groups':[],'ingress_host':'foundry.example.invalid','tls_secret_ref':'REPLACE_TLS_SECRET'}}}
write('contracts/example-config.json',json.dumps(example,indent=2))

write('checklists/plan.md','''
# Planning Quality Checklist: Foundry-v2

Date: 2026-10-10. Feature: [plan.md](../plan.md). This validates design artifacts, not live implementation behavior.

- [x] Existing feature directory reused; DRAFT/operator decisions unchanged.
- [x] Technical context selects language, process boundaries, version pins, storage and tests.
- [x] Research decisions have primary source links and documented alternatives.
- [x] Eleven constitutional principles pass pre- and post-design review without exceptions.
- [x] Entities include keys, relationships, constraints, state transitions and crash semantics.
- [x] HTTP contracts define operator/agent security, DTOs, idempotency and error semantics.
- [x] Configuration schema and placeholder example are supplied; semantic checks remain explicit.
- [x] Remote checkpoint ownership, claim fencing and single-evaluation ownership are defined.
- [x] Kubernetes/Cilium admission, additive-policy, storage and UID-0 probe caveats are explicit.
- [x] GitHub lost-response reconciliation is fail-closed rather than a blind POST retry.
- [x] Provider/tool/token checks and local estimated rates handle unknown/zero accounting.
- [x] Quickstart identifies commands as planned, includes prerequisites and acceptance outcomes.
- [x] No credentials, deployments or external issue writes were performed.
- [x] Agent context points to this plan; optional context hook executed.
- [x] No unresolved design placeholders; required environment values are deployment inputs.

Dependency pins are metadata-verified, not a resolved/tested lock. Cluster/GPU/storage/identity checks remain unexecuted implementation/deployment gates. Tasks and application code are deliberately subsequent workflow phases.
''')
print(json.dumps({'artifacts':'plan, research, data model, quickstart, API/config/runtime contracts, plan checklist','http_paths':len(api['paths']),'operations':sum(len(v) for v in api['paths'].values()),'schemas':len(schemas)},indent=2))
