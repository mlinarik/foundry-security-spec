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
