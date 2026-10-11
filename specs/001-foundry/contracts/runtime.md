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
