# Foundry-v2: AI-Assisted Security Evaluation Framework

| Field | Value |
|---|---|
| **Status** | `DRAFT` |
| **Version** | 0.2.0 |
| **Updated** | 2026-10-10 |
| **Intended use** | Implementation requirements and acceptance criteria; ready for `speckit-plan`. |
| **Companion files** | `.specify/memory/constitution.md`; see `README.md` for usage |

> **Foundry-v2 implementation specification.** Derived from the Foundry seed, with all operator decisions recorded below. The constitution at `.specify/memory/constitution.md` version 0.2.0 remains authoritative. This DRAFT defines required behavior; planning selects implementation details within the adopted constraints.

**System name**: Foundry-v2. Use this name in CLI commands, configuration file names, issue labels, log prefixes, and user-facing documentation.

---

## Clarifications

### Session 2026-10-09

- Q: What should your system be called? → A: Foundry-v2.
- Q: Will the system evaluate software you have source code and authorization to test? → A: Yes; source access and authorization are required.
- Q: Should Foundry-v2 keep all eight core roles? → A: Yes; retain each as a distinct role without merging, splitting, or omission.
- Q: Should the first build include any optional extensions? → A: Core only; defer Deep-Tester, Variant-Hunter, Attack-Mapper, Remediator, and Self-Improver.
- Q: Where should Foundry-v2 run initially? → A: One operator-controlled machine; single tenant with one evaluation at a time.
- Q: Which version-control host and issue tracker should Foundry-v2 use? → A: GitHub repositories and GitHub Issues.
- Q: Which datastore should hold findings, the work queue, index, and coverage state? → A: SQLite.
- Q: Will evaluations have a running test deployment for validation? → A: Optional; available for some evaluations.
- Q: Which LLM provider should Foundry-v2 use? → A: Ollama API.
- Q: Which source languages must Foundry-v2 analyze in its first build? → A: Python and Go.
- Q: How should Foundry-v2 isolate agents and test execution? → A: Kubernetes instance with read-only mounts; network enforcement remains open.
- Q: How should outbound network access be restricted to authorized destinations? → A: Kubernetes NetworkPolicies enforced by the cluster network plugin.
- Q: Where will the Kubernetes instance run? → A: An existing shared cluster with a dedicated evaluation namespace; supersedes the earlier single-machine topology.
- Q: How should the Orchestrator run? → A: A persistent service in Kubernetes that the operator connects to.
- Q: How should agents access the datastore across cluster nodes? → A: One substrate service owns SQLite; agents use its API.
- Q: Which Ollama model or models should Foundry-v2 use? → A: qwen3-coder:30b for all LLM-backed roles.
- Q: Where will the Ollama API run? → A: On a separate GPU server reachable from the Kubernetes cluster.
- Q: Which API interface should Foundry-v2 use? → A: Native Ollama API.
- Q: Which Kubernetes network plugin enforces NetworkPolicies in the shared cluster? → A: Cilium.
- Q: How should hostname-based destinations such as GitHub and Ollama be allowed? → A: Explicit IP/CIDR rules maintained by the operator.

### Session 2026-10-10

- Q: How should Foundry-v2 connect to the separate Ollama GPU server? → A: Private-network HTTP without API authentication.
- Q: How should Foundry-v2 authenticate to GitHub? → A: Dedicated service-account token.
- Q: Which agent harness should run the LLM tool-use loops? → A: A graph-based framework; specific framework remains open.
- Q: Which graph-based framework should Foundry-v2 use? → A: LangGraph for Python.
- Q: Should the first build include semantic code search using embeddings? → A: Defer embeddings and vector search; retain structural indexing.
- Q: Which detection techniques should the first build include? → A: All four: rule-based analysis, dependency scanning, secret scanning, and exploratory hunting.
- Q: How should the detection-rule corpus be maintained? → A: Start with CodeGuard, add organization-specific rules, and maintain the corpus in a versioned Git repository.
- Q: How should the Triager investigate candidate findings? → A: An open-ended tool-use loop guided by a fixed investigation checklist.
- Q: Should needs-review findings create GitHub issues? → A: No; keep needs-review internal and publish only true-positive findings.
- Q: How should the dashboard be delivered? → A: A web UI served by the Orchestrator.
- Q: Should the Cartographer delay other agents while building the security map? → A: No; start other agents after the Indexer is ready.
- Q: How should the Cartographer produce its documents? → A: Focused passes, one per document type.
- Q: Which weakness taxonomy should finding reports use? → A: CWE, with ID, name, and evidence-supported mapping rationale.
- Q: Which severity scheme should reports use? → A: CVSS 4.0 score and vector.
- Q: Should findings also be exported beyond GitHub Issues? → A: No; GitHub Issues only for the first build.
- Q: How should optional testbeds be described and managed? → A: Operator provisions and resets them; agents receive a structured inventory of endpoints, access requirements, and scope.
- Q: Which configuration format should Foundry-v2 use? → A: YAML.
- Q: Must findings map to a compliance or control framework? → A: No compliance mapping in the first build; retain CWE and CVSS.
- Q: How will report readers access linked GitHub source? → A: The operator grants access to source and reporting repositories before sharing reports.
- Q: What policy header should PoC artifacts carry beyond setup prerequisites? → A: Authorized testing only notice; no added license or classification.
- Q: Adopt the proposed GitHub label names and colors? → A: Yes; use foundry-v2, verdict:true-positive, severity tiers, exploited:yes/no, cwe:<ID>, and in-progress with the specified colors.

## 1. Purpose & Scope

### 1.1 The problem this solves

A team has access to a tool-capable LLM and a piece of software they need to evaluate for security defects. Pointing the model at the codebase and asking "find the bugs" does not work: the output is unbounded, unverifiable, mostly noise, and there is no way to know when the job is done.

Foundry-v2 is the scaffolding that turns a tool-capable LLM into a security evaluation system that produces a bounded, verifiable, prioritized set of findings, and can tell you when it has finished.

### 1.2 What the system does

Given a target (source code, optionally a running deployment of that code, and a statement of evaluation goals), Foundry-v2:

1. Builds a structured understanding of the target: a code index, and a set of security-context documents (architecture, attack surface, trust boundaries, threat model).
2. Runs a fleet of LLM-backed agents that hunt for vulnerabilities using whatever techniques are available: applying detection rules function by function, scanning dependencies, reading code, probing the running deployment.
3. Investigates each candidate finding to separate real vulnerabilities from noise, using both code evidence and (where possible) live reproduction.
4. Writes up confirmed findings in a form a human can act on, with severity, classification, and reproduction steps.
5. Tracks coverage against the stated goals and stops itself when the work is done.
6. Keeps a human operator informed and in control throughout.

### 1.3 What "done" looks like

An evaluation is done when **both** of the following hold:

- **Coverage is complete**: every goal the operator stated has been credibly attempted (not necessarily with findings; "we looked and found nothing" satisfies coverage).
- **Yield has decayed**: the rate of new confirmed findings per unit of cost has fallen below a threshold the operator set.

Neither condition alone is sufficient. A system that stops on low yield before covering the stated goals has not done the job. A system that keeps running after coverage is complete and yield has flatlined is wasting money.

*Rationale: a recurring failure mode in early iterations was agents that either declared victory after a shallow pass ("everything is covered") or ran indefinitely with no stopping criterion at all. Making "done" a conjunction of an operator-defined floor (coverage) and an economic signal (yield) fixed both. See §9.*

### 1.4 In scope

- Security evaluation of software for which the operator has source code, authorization to test, and (optionally) a deployed instance to test against.
- Python and Go source evaluation; one active evaluation at a time. Multi-target scope is processed within that evaluation, not as concurrent evaluations.
- Operator-driven and fully autonomous operation, and everything in between.

### 1.5 Out of scope

See §14.

**Evaluation scope**: Foundry-v2 evaluates software for which the operator has source access and authorization to test.

### 1.6 Success Criteria

These are technology-agnostic, measurable outcomes a Foundry-v2 implementation must demonstrate before it is considered fit for production use. Each is a pass/fail observable, not a target metric to optimize. The acceptance thresholds below apply to this DRAFT.

| ID | Criterion | Validates |
|---|---|---|
| **SC-001** | On a target with at least one known seeded vulnerability, an end-to-end run produces a published `true-positive` finding for it with evidence satisfying §7.3, with no operator intervention between evaluation start and publication. | US-1, US-7, FR-054, FR-089 |
| **SC-002** | Of all findings published `true-positive` over a representative evaluation, ≥90% are confirmed real on human review (precision floor). | US-7, FR-054, Constitution I |
| **SC-003** | No finding carrying the `exploited` flag fails independent human reproduction of its headline impact using only the PoC artifact. | US-8, FR-063, Constitution VII |
| **SC-004** | Killing any single agent process at any point leaves no work unit permanently stranded: its claim is released and re-acquired by a peer within the configured heartbeat-stale threshold plus one monitoring cycle, with no operator action. | FR-099, FR-104, NFR-001, Constitution III/IV |
| **SC-005** | A second run on an unchanged target produces zero new issue-tracker issues and zero duplicate findings in the store. | US-11, FR-093, FR-094, NFR-002 |
| **SC-006** | An evaluation with both budget caps unset and a `goals` document covering the full target halts on its own (coverage-complete ∧ yield-below-threshold) without operator stop. | US-4, FR-073, FR-127, Constitution VI |
| **SC-007** | An agent inside the sandbox, given root and an explicit instruction to do so, cannot open a connection to a host outside the configured allowlist. | US-6, FR-118, Constitution IX |
| **SC-008** | Operator status query and dashboard report identical fleet state, finding counts, and budget figures at the same instant. | US-2, FR-009, FR-139, FR-143 |
| **SC-009** | For any published finding, the full provenance chain (detection technique → triage transcript → validation attempt → report render) is reconstructable from logs alone. | NFR-006, FR-141 |

### 1.7 Assumptions

These dependencies and assumptions constrain this build. Capability checks validate the selected deployment before evaluation startup.

| ID | Assumption | If false |
|---|---|---|
| **A-1** | The operator is authorized to evaluate the target and to probe the testbed; authorization is established outside the system. | Out of scope (§14). |
| **A-2** | The operator has read access to the target's source code. | §1.5 clarification; black-box mode is out of scope (§14). |
| **A-3** | The selected Ollama model exposes tool/function calling and per-call token counts; capability and quality checks must pass before production evaluation. | §11.2 capability check; report failure without silently changing models. |
| **A-4** | The deployment environment can enforce network-egress and filesystem-write boundaries below the agent process (i.e., not by prompt alone). | §9.1 / §11.6 clarification; "trust the prompt" is rejected by FR-118. |
| **A-5** | The operator is a security engineer comfortable reading code, editing a config file, and interpreting a vulnerability writeup; the system does not target non-technical users. | Persona table §3.1. |
| **A-6** | A single evaluation's working set (index, finding store, queue, logs) fits in storage reachable by every agent in the fleet. | §11.3 / §11.5 clarifications. |
| **A-7** | Wall-clock latency of an individual LLM call is acceptable to be seconds-to-minutes; the system is throughput-oriented, not interactive-latency-oriented. | Affects §5.1 conversational facet expectations only. |
| **A-8** | The issue tracker (or equivalent) supports labels, comments, and programmatic create/update. | The selected GitHub repositories must allow the service account to perform the §11.1 contract. |
| **A-9** | Detection rules are expressible as natural-language checks an LLM can evaluate against a function body plus call-graph context (not as compiled static-analysis queries). | §5.4 rule-corpus clarification. |

---

## 2. Glossary

| Term | Definition |
|---|---|
| **Target** | The software under evaluation: its source code, and optionally a running deployment of it (the *testbed*). |
| **Testbed** | A running instance of the target that agents may probe and exploit. May be absent. |
| **Operator** | The human who configures, starts, steers, and stops an evaluation. |
| **Evaluation goals** | The operator's written statement of what outcomes matter (e.g. "authentication bypass", "RCE on the control plane") and what is in scope to test. |
| **Agent** | An LLM-backed worker with a defined role, running in a loop, coordinating with peers via the shared substrate. |
| **Role** | A named agent specialization (Detector, Triager, etc.). One role may have many concurrent instances. |
| **Fleet** | All agent instances currently running for one evaluation. |
| **Finding** | A claimed vulnerability at any lifecycle stage, from "candidate" through "confirmed and reported". |
| **Candidate** | A finding that has been detected but not yet investigated. |
| **Verdict** | The Triager's classification of a candidate: `true-positive`, `false-positive`, `needs-review`, `not-applicable`, or `code-quality`. |
| **Evidence gate** | The structural requirement a finding must satisfy before it may be classified `true-positive`. See §7.3. |
| **Exploited** | A `true-positive` finding whose headline impact has been independently reproduced against the testbed by a clean-room check. See §7.4. |
| **Fingerprint** | A stable identifier for a finding, used for deduplication across runs. See §7.5. |
| **Finding report** | The human-readable writeup of a confirmed finding: description, impact, reproduction, severity, classification. |
| **Security map** | The Cartographer's output: architecture overview, attack-surface enumeration, trust-boundary map, data-flow description, threat model. |
| **Detection rule** | A reusable, versioned check for one vulnerability class, applied by the Detector to each function in scope. The rule corpus is an artifact independent of the agent code. |
| **Rule-gap** | A record that an exploratory finding was confirmed `true-positive` and no detection rule would have produced it; the input to growing the rule corpus. See FR-044. |
| **Coverage** | The degree to which the evaluation goals have been credibly attempted. |
| **Yield** | Severity-weighted confirmed findings per unit of spend, measured over a trailing window. |
| **Work queue** | The shared, ordered list of tasks agents claim from. See §8. |
| **Finding store** | The durable, fingerprint-indexed record of every finding at every lifecycle stage; internal, queryable by every role. Distinct from the issue tracker. |
| **Coverage log** | The append-only record of which (area × technique) pairs the fleet has attempted; an audit trail, not a stop-list. See FR-048. |
| **Budget governor** | The substrate component that tracks spend, runtime, and trailing yield against operator caps and signals the Orchestrator to halt. See §9.3–§9.4. |
| **Help request** | An operator-filed issue asking the fleet to perform a specific action; resolved by the Orchestrator's conversational facet. See FR-016. |
| **Operator message** | An agent-authored, asynchronous, one-way note to the operator (blocker, request, feedback, or informational), deduplicated across the fleet. The agent→operator counterpart of a help request. See FR-107. |
| **Proof-of-concept (PoC)** | A self-contained, runnable artifact that demonstrates a finding's headline impact against the testbed. See FR-065. |
| **Claim** | An agent's exclusive, crash-safe hold on a unit of work (a task, a finding, a target file). |
| **Substrate** | The non-agent machinery every role depends on: work queue, finding store, sandbox, budget tracker, dashboard. |
| **Index** | The structured representation of the target's source: symbols, call graph, cross-references. |
| **Sandbox** | The isolation boundary around the agent fleet that constrains what it can reach and modify. |

---

## 3. Personas & User Stories

### 3.1 Personas

| Persona | Who they are | What they need from Foundry-v2 |
|---|---|---|
| **Operator** | Security engineer running the evaluation. Configures the target, starts/stops the fleet, reviews output, answers agent questions. | Low-friction setup; visibility into what the fleet is doing and why; confidence that findings are real; a clear "done" signal. |
| **Reviewer** | Security architect or product owner who reads the output. Did not run the tool. | A bounded, prioritized list of findings they can assign and act on; not a thousand unranked issues. |
| **Target developer** | Engineer who owns code a finding was filed against. | Enough detail in each finding to reproduce and fix it without talking to the operator. |
| **Builder** | You: the engineer turning this seed into a working system for your organization. | A clear shape to build against, with the dangerous defaults already chosen correctly. |

### 3.2 User stories

The system MUST support the following user stories. Each is satisfied by one or more FRs in §5–§12; the satisfying FRs cite the story by ID.

| ID | Pri | As a... | I want to... | So that... | Independent test |
|---|---|---|---|---|---|
| **US-1** | P1 | Operator | Point the system at a target repository and a one-page goals document, run one command, and walk away | An evaluation starts without me hand-assembling a pipeline | From a fresh checkout + valid config, `up` reaches "fleet running, index queryable" with no further input. |
| **US-2** | P1 | Operator | See, at any moment, what every agent is working on, what it has found, and what it is blocked on | I can intervene when something goes wrong instead of discovering it at the end | `status` and dashboard each enumerate every live agent with its current claim. |
| **US-3** | P2 | Operator | Ask the running system a free-form question ("why was finding #14 closed?", "has anyone looked at the auth module?") and get an answer grounded in the evaluation's actual state | I do not have to read raw logs | A query about a known finding's verdict returns the recorded reasoning with a citation to the store record. |
| **US-4** | P1 | Operator | Be told when the evaluation is done, and why | I am not guessing when to stop paying for compute | SC-006. |
| **US-5** | P1 | Operator | Set a hard ceiling on spend and/or wall-clock time | A runaway evaluation cannot cause an unbounded bill | With a low spend cap set, fleet halts within one polling interval of the cap being crossed; FR-012 refuses restart. |
| **US-6** | P1 | Operator | Constrain what the agent fleet can reach on the network and modify on disk | Agents probing a live deployment cannot accidentally reach production, the internet, or their own configuration | SC-007. |
| **US-7** | P1 | Reviewer | Receive only findings that have passed a structural evidence check, with the evidence attached | I am not triaging the model's hallucinations | SC-002; every published issue carries resolvable §7.3 citations. |
| **US-8** | P2 | Reviewer | See which findings were actually demonstrated against a running system, distinct from those only argued from code | I can prioritize what is proven over what is plausible | SC-003. Depends on a testbed (§11.12). |
| **US-9** | P2 | Reviewer | Receive a single rollup that groups findings by component, prioritizes confirmed findings by severity and exploitation evidence, and maps coverage against the original goals | I can brief stakeholders and assign work without reading every finding | Rollup lists each scoped component with its finding count (including zero) and coverage evidence. |
| **US-10** | P1 | Target developer | Open any single finding and find a self-contained description, reproduction steps, and (where one exists) a runnable proof-of-concept | I can fix it without chasing the operator for context | A developer with repo access but no system access can reproduce a sampled `exploited` finding from its issue alone. |
| **US-11** | P2 | Operator | Re-run the evaluation after the target changes and have prior findings deduplicated rather than re-filed | The second run's output is the delta, not a duplicate of the first | SC-005. |
| **US-12** | P2 | Operator | Hand a specific task to the fleet ("investigate function X", "try to reproduce issue #N") and have an agent pick it up | I can steer without restarting | An operator-queued task is claimed by an agent of the addressed role within one claim cycle. |
| **US-13** | P3 | Builder | Swap any one of the integration choices (issue tracker, LLM provider, datastore, deployment target) without redesigning the agent roles | The system fits my organization's existing infrastructure | Replacing the §11.1 binding with an alternate satisfying the same contract requires no change to any §5 role. |
| **US-14** | P3 | Builder | Take the detection rule corpus this system accumulates and deploy it elsewhere as development-time guardrails | Investment in detection compounds into prevention | The rule corpus (FR-043) loads unchanged into at least one external consumer. |

**Priority rationale.** P1 = without this the system is unsafe to run or its output is untrustworthy (US-1, 2, 4, 5, 6, 7, 10). P2 = materially improves operator efficiency or reviewer confidence but the system is usable without it (US-3, 8, 9, 11, 12). P3 = portability and compounding value; realized after the core works (US-13, 14).


### 3.3 Edge Cases

| Case | Expected behavior | Governed by |
|---|---|---|
| Agent process killed mid-claim | Claim auto-released within heartbeat-stale threshold plus one monitoring cycle; work re-queued; no operator action. | FR-099, FR-104, SC-004 |
| Two agents claim simultaneously | Exactly one wins; the other receives a different unit or "none". | FR-098, Constitution IV |
| LLM provider returns 429 / quota exhausted | Fleet-wide adaptive backoff; dashboard surfaces degraded state; no internal cap added. | FR-115, FR-116, FR-144, NFR-004 |
| Crash between "delete old" and "write new" on a persisted artifact | Cannot occur: write-new-then-swap only. | FR-117, Constitution XI |
| Index incomplete when a downstream role queries it | Role degrades gracefully; FR-025 gate prevents fleet spawn before minimum index is queryable. | FR-004, FR-025, FR-037 |
| Goals document is empty / placeholder | Coverage-Guide waits and re-checks; never synthesizes goals. | FR-070 |
| Triager cites a code location that does not exist | Verdict auto-demoted to `needs-review`. | FR-091 |
| Target source contains adversarial instructions ("ignore previous instructions and …") | Treated as untrusted content; sandbox enforces boundaries regardless of prompt state. | NFR-009, FR-118, Constitution IX |
| Task fails N consecutive claim/release cycles | Auto-transitions to `blocked`; surfaced for operator/Coverage-Guide review. | FR-100 |
| Re-run after target edit shifts every line number | Fingerprints (path+symbol+class) survive; no duplicate issues filed. | FR-093, FR-094, SC-005 |
| Operator overrides an automated verdict | Override applied and recorded; system does not refuse. | NFR-008, FR-019, Constitution Governance |
| No testbed configured | Validator degrades to PoC-only; `exploited` is never set. | FR-068 |
| Budget caps both unset | Pre-flight warns; run is unbounded by spend/time, bounded only by coverage∧yield. | FR-125, FR-127 |
| Agent exceeds soft session limit | Steered to wrap up and release claims. | FR-129 |
| Agent exceeds hard session limit | Process terminated; fresh instance spawned in slot; any claim still held is released by FR-099, not re-queued by the rotation itself. | FR-129, FR-099, Constitution III |
| Agent hits a human-only blocker | Agent posts an operator message (`kind=blocker`/`request`), releases any held claim, continues with other work; does not wait for a reply. | FR-107 |
| Multiple agents post equivalent operator messages | Second and subsequent posts suppressed by dedup; posting agent receives the existing message id. | FR-108 |
| Agent discovers follow-on work outside its current claim | Agent queues a new task and continues its held work; does not pursue inline or peer-steer. | FR-102 |

---


### 3.4 User Scenarios & Testing

The prioritized story table above defines user value and independent test boundaries. Each scenario below is independently exercisable with deterministic fixtures for adjacent stages; integration acceptance additionally uses the selected deployed bindings.

#### US-1: Start an authorized evaluation (P1)

- **Given** valid YAML, GitHub access, pinned Python/Go source, approved policies, and a compatible Ollama endpoint, **When** the operator starts an evaluation, **Then** one Indexer starts first; no other role starts until its required queries succeed; the remaining core roles then start without waiting for cartography.

#### US-2: Inspect live progress (P1)

- **Given** a running evaluation with live, blocked, and restarted agents, **When** the operator opens status and dashboard for the same snapshot, **Then** both show identical claims, heartbeat ages, counts, budget, and blockers; activity can be filtered by role and event.

#### US-3: Ask grounded questions (P2)

- **Given** a triaged finding and its durable evidence transcript, **When** the operator asks why its verdict was assigned, **Then** the answer cites the actual stored reasoning; a delayed model answer does not delay lifecycle handling.

#### US-4: Recognize honest completion (P1)

- **Given** a configured positive cost model and a finite goal checklist, **When** yield falls below threshold after the full window and minimum runtime, **Then** the fleet drains only if every coverage item is complete; changing goals clears completion.

#### US-5: Bound resource use (P1)

- **Given** a configured spend or runtime cap, **When** the ledger or elapsed runtime exceeds it, **Then** the Orchestrator begins halting within one monitoring cycle and rejects restart until the relevant cap is raised.

#### US-6: Enforce authorized boundaries (P1)

- **Given** Cilium-enforced IP/CIDR policy and read-only protected mounts, **When** an agent with container-root access attempts denied egress, source writes, or policy changes, **Then** all attempts fail at infrastructure boundaries; failure of the preflight boundary check prevents agent startup.

#### US-7: Publish evidence-backed findings (P1)

- **Given** candidates with valid evidence, fabricated citations, and incomplete evidence, **When** triage and reporting run, **Then** only verified true-positive findings create GitHub issues; invalid citations demote to needs-review and nonconfirmed findings stay internal.

#### US-8: Distinguish demonstrated impact (P2)

- **Given** a true-positive finding and optional authorized testbed, **When** a fresh Validator receives the artifact and claim, **Then** only observed headline impact sets exploited; failed or partial reproduction records its reason; no testbed yields an unexecuted artifact and no exploited flag.

#### US-9: Review a useful rollup (P2)

- **Given** scoped components with confirmed findings and components with no findings, **When** the Reporter refreshes the rollup, **Then** every component has counts and coverage evidence, findings are prioritized by severity/exploitation, and no unsupported attack-chain claim is made.

#### US-10: Reproduce from one report (P1)

- **Given** a reader granted repository access and an independently exploited finding, **When** the reader follows the published issue and artifact, **Then** pinned code links resolve and the reported impact can be reproduced with documented prerequisites and the Authorized testing only notice.

#### US-11: Rerun without duplicates (P2)

- **Given** prior findings and a target edit that shifts lines without changing path, symbol, or weakness class, **When** the evaluation is rerun, **Then** only changed files are re-parsed, stable fingerprints retain identity, and GitHub issues are updated rather than recreated.

#### US-12: Steer active work (P2)

- **Given** a running agent with a claim and an operator-authorized request, **When** the operator queues a task or sends immediate/idle steering, **Then** the task is eligible in the next claim cycle, steering respects its requested mode, and peer advice never gains operator authority.

#### US-13: Keep roles independent of bindings (P3)

- **Given** an integration adapter satisfying its documented contract, **When** the builder substitutes a test adapter, **Then** role contract tests pass without changing role behavior; adding alternative production integrations is not required for this build.

#### US-14: Reuse the rule corpus (P3)

- **Given** a pinned CodeGuard corpus with reviewed organization-specific additions, **When** the builder loads it in an external compatible consumer, **Then** the same rule content is consumed unchanged and each evaluated finding retains corpus provenance; no Self-Improver is required.

Additional boundary acceptance: a prolonged but heartbeating call retains its claim; after real heartbeat expiry reclamation occurs on the next monitor cycle. Concurrent claim attempts never share a task. Fault injection during publication reconciles one issue; during persistence readers see the previous or next complete generation. Loss of Ollama, GitHub, or substrate connectivity surfaces degradation and preserves committed progress.


### 3.5 Key Entities

| Entity | Required attributes and relationships |
|---|---|
| Evaluation | Stable ID, pinned target revisions, goals, config revision, corpus revision, lifecycle state, one-active-evaluation ownership, budget and coverage snapshots. |
| Agent session | Evaluation ID, role, instance/session IDs, heartbeat, restart count, checkpoint and current claim; no secret values in logs. |
| Work task and claim | Stable task ID independent of priority; description, role, state and release count; exclusive holder linked to heartbeat liveness. |
| Finding | Stable structural fingerprint, target location, candidate technique, one verdict, evidence citations, validation status, report revision and GitHub issue identity. |
| Index generation and security document | Evaluated revision, scoped Python/Go code units and edges or document type, completeness/error metadata and atomic generation ID. |
| Coverage item and attempt | Component and operator goal, explicit attempt bar, supporting activity references, closure state; attempts are not authoritative completion claims. |
| Budget entry | Idempotent model-call ID, role, token counts or unknown status, configured rates, estimated currency amount and elapsed runtime. |
| Operator message and audit event | Origin, kind, dedup identity, acknowledgment, operator authority or agent-advisory provenance, timestamp and referenced records. |
| Testbed inventory | Operator-authorized endpoints, ports, protocols, scope, secret references and operator-managed reset procedure; optional per evaluation. |

## 4. System Overview

### 4.1 Shape

Foundry-v2 is a **fleet of role-specialized LLM agents** coordinated through a **shared substrate**, supervised by an **orchestrator**, operating on a **target** within a **sandbox**. The operator interacts with the system through one surface, the Orchestrator, for both lifecycle control (start, stop, configure, status) and conversational access (ask about findings, queue work, steer agents).

```
                                   OPERATOR
                                      │
                       ┌──────────────▼──────────────┐
                       │        ORCHESTRATOR         │
                       │  lifecycle: validate ·      │
                       │  spawn · maintain · status  │
                       │  converse: Q&A · steer ·    │
                       │  queue tasks · help reqs    │
                       └──────────────┬──────────────┘
                                      │
                       ══════════ SUBSTRATE ══════════
                        work queue · finding store ·
                        sandbox · budget · dashboard
                       ══════════════╤════════════════
                                     │
       knowledge layer               │   finding pipeline                  oversight
   ┌─────────┬─────────┐             │ ┌────────┬────────┬─────────┐   ┌────────┬─────────┐
   ▼         ▼         │             │ ▼        ▼        ▼         │   ▼        ▼         │
┌───────┐┌─────────┐   │           ┌────────┐┌────────┐┌─────────┐ │┌────────┐┌─────────┐ │
│INDEXER││ CARTO-  │───┘           │DETECTOR││TRIAGER ││VALIDATOR│ ││REPORTER││COVERAGE │ │
│       ││ GRAPHER │               │        ││        ││         │ ││        ││ GUIDE   │ │
└───┬───┘└────┬────┘               └───┬────┘└───┬────┘└────┬────┘ │└───▲────┘└────┬────┘ │
    └─────────┴─── feeds every ────────┘         │          │      │    │          │      │
              role below             candidates  verdicts  exploited    │       done?     │
                                         └───────────┴────────┴─────────┴──────────┴──────┘

           ─ ─ ─ ─ extension roles (deferred; out of scope) ─ ─ ─ ─
           DEEP-TESTER · VARIANT-HUNTER · ATTACK-MAPPER · REMEDIATOR · SELF-IMPROVER
```

The arrows show the **primary** data flow. They are not the only flow: every role reads and writes the substrate, and any role may queue work for any other.

### 4.2 The eight core roles

| Role | One-line responsibility | Specified in |
|---|---|---|
| **Orchestrator** | The operator's sole interface: validate configuration, spawn and maintain the fleet, expose status, enforce budget; and answer operator questions, accept tasks and steering, resolve help requests. One role, two facets that must not block each other. | §5.1 |
| **Indexer** | Build and maintain the code index: symbols, call graph, cross-references. The structural knowledge every other role queries. | §5.2 |
| **Cartographer** | Build and maintain the security map: architecture overview, attack-surface enumeration, trust boundaries, data flows, threat model. The contextual knowledge every other role reasons against. | §5.3 |
| **Detector** | Produce candidate findings by both systematic rule application and free-form exploration. Breadth-first. | §5.4 |
| **Triager** | Investigate each candidate and assign a verdict, gated on structural evidence. The noise filter. | §5.5 |
| **Validator** | For every confirmed finding with a configured testbed, independently attempt to reproduce the headline impact in a clean room. The proof filter. | §5.6 |
| **Coverage-Guide** | Translate the operator's goals into a checklist, track the fleet's progress against it, declare coverage complete. Half of the "done" signal. | §5.7 |
| **Reporter** | Produce the human-facing output: per-finding writeups with severity and classification, and the evaluation-level rollup. | §5.8 |

*Rationale for this decomposition: each role has a distinct **failure mode** that the next role exists to catch. Indexing without cartography gives agents structure with no security context. Detection without triage produces noise. Triage without validation produces plausible-sounding fiction. Validation without coverage produces a pile of confirmed bugs with no claim to completeness. Reporting without a conversational interface produces a wall of text the operator cannot interrogate. We arrived at this set by repeatedly discovering that merging any two of them caused the merged role's quality bar to drift toward the weaker of the two.*

**Core role decomposition**: Foundry-v2 retains all eight core roles as distinct roles: Orchestrator, Indexer, Cartographer, Detector, Triager, Validator, Reporter, and Coverage-Guide. No core roles are merged, split, or omitted.

### 4.3 The five extension roles

All five extensions below are excluded from the first build as recorded in §6. Each is a capability the authors found valuable **after** the core pipeline was producing trustworthy findings; building any of them before that point is premature.

| Role | Adds |
|---|---|
| **Deep-Tester** | Input-generation testing (fuzzing, property-based testing) against specific functions or endpoints, typically ones the core pipeline already flagged. Depth where Detector gave breadth. |
| **Variant-Hunter** | Given one confirmed finding, search the rest of the target for the same pattern. |
| **Attack-Mapper** | Assemble confirmed findings into a privilege graph showing how they chain from attacker entry points to operator-defined goals. |
| **Remediator** | Generate and verify candidate patches for confirmed findings. |
| **Self-Improver** | Read the fleet's own logs, metrics, and rule-gap records; propose configuration, prompt, and detection-rule changes to the operator. |

### 4.4 The substrate

Not agents; the machinery every agent uses. Specified as **behavior** in §8-§10, not as implementation.

| Component | Guarantees it must provide |
|---|---|
| **Work queue** | Ordered tasks; atomic claim; crash-safe release on holder death; bounded retry with auto-block. |
| **Finding store** | Durable record of every finding at every lifecycle stage; fingerprint-indexed; queryable by every role. |
| **Sandbox** | Network egress constrained to an allowlist; filesystem write constrained to designated paths; survives agent root. |
| **Budget governor** | Tracks spend and runtime against operator-set caps; computes trailing yield; halts the fleet on cap or on yield-below-threshold once coverage is complete. |
| **Dashboard** | Operator-facing live view of fleet state, findings, coverage, budget, yield. |

### 4.5 What an evaluation looks like end to end

1. Operator writes a configuration: where the target source is, where (if anywhere) the testbed is, what the goals are, what is in and out of scope, budget caps.
2. Operator invokes the Orchestrator. Orchestrator validates the config, stands up the substrate, spawns one Indexer.
3. Indexer builds the code index. When it is queryable, Orchestrator spawns the Cartographer and the rest of the fleet.
4. Cartographer reads the index, the source, the testbed description, and the goals; writes the security map. Other roles read whatever portion of the map exists at the time they need it; they degrade gracefully if it is incomplete.
5. Detector instances sweep the target (rules, function by function) and explore it (free-form, against goals and security map); both queue candidates into the finding store. Coverage-Guide builds its checklist from the goals and the security map and starts queueing directed tasks.
6. Triager instances claim candidates, investigate (using index and security map for context), assign verdicts. Every `true-positive` verdict is queued for Validator; testbed availability determines live reproduction or the documented no-testbed path. All verdicts are visible to Reporter.
7. Validator attempts clean-room reproduction; marks findings `exploited` or records why not.
8. Reporter writes up each confirmed finding as it lands and maintains the rollup.
9. Coverage-Guide watches the finding store and work queue, checks off goals as they are credibly attempted, eventually marks coverage complete.
10. Budget governor watches yield. Once coverage is complete **and** trailing yield is below threshold (or a hard cap is hit), it signals the Orchestrator, which drains the fleet and stops.
11. Throughout, the Operator can ask the Orchestrator questions, queue tasks, steer agents, adjust scope, or stop early.

*Rationale: step 3's "index first, then spawn the rest" gate exists because every downstream role's quality depends on being able to ask "who calls this function" and "where is this symbol defined". Early versions that ran detection in parallel with indexing produced findings that could not be investigated because the investigation tools had nothing to query. The gate costs minutes and saves hours. The Cartographer does not gate the fleet per §5.3: its outputs improve every downstream role's reasoning, but unlike the index they are not strictly required for those roles to function, and on large targets the map can take materially longer to produce. This build has no Cartographer gate; roles read whatever map exists when they need it.*

### 4.6 Adopted constraints and planning boundary

The system uses the integration choices in §11: shared-cluster Kubernetes, Cilium IP/CIDR policies, one SQLite-owning substrate service, a persistent Orchestrator web service, native Ollama on a separate GPU server, `qwen3-coder:30b`, LangGraph for Python, and GitHub. These are operator-adopted constraints, not proposed alternatives.

Planning must choose concrete schemas, endpoint routes, storage classes, dependency versions, parsers, scanner integrations, and deployment manifests that satisfy these contracts. Operator-authored prompts, CodeGuard extensions, goals, rates, and scope are versioned configuration inputs; their actual content is not inferred by this specification.

---

## 5. Core Agent Roles

Each role below is specified as: purpose, triggers, inputs, outputs, functional requirements, invariants, rationale, and the cost of omitting, merging, or splitting it. Functional requirements are numbered `FR-NNN` and referenced from `tasks.md` after `/speckit.tasks` runs.

Throughout this section, "MUST" denotes a required first-build behavior; "SHOULD" means strongly recommended but a viable system could defer it; "MAY" means optional.

### 5.1 Orchestrator

**Purpose.** The operator's sole interface to the system, in both modes: **lifecycle control** (validate configuration, stand up the substrate, spawn and maintain the fleet, expose status, enforce budget, shut down cleanly) and **conversational access** (answer questions about evaluation state, accept operator tasks and steering, resolve help requests). One role, two facets; the facets must not block each other.

**Triggers.** Operator command (`init`, `up`, `down`, `status`, `pause`, `resume`); operator message or help request; budget governor signals (cap reached, yield below threshold); agent death (respawn).

**Inputs.** Evaluation configuration (§12); fleet state from substrate; budget/yield from governor; full read access to finding store, work queue, coverage state, agent logs, index, and security map (for conversational queries).

**Outputs.** Running fleet; status reports; lifecycle events to dashboard; answers to operator; tasks queued; help-request issues resolved.

**Functional requirements: lifecycle.**

- **FR-001**: The Orchestrator MUST validate the evaluation configuration before spawning any agent, refusing to start with a specific, actionable error if validation fails. (US-1)
- **FR-002**: The Orchestrator MUST be the only component that spawns or terminates agent processes.
- **FR-003**: Agents MUST NOT spawn peer agents directly.
- **FR-004**: The Orchestrator MUST gate the spawn of all non-Indexer roles on the Indexer reporting its knowledge base as queryable. *Rationale: every downstream role's investigation quality depends on "who calls this" and "where is this defined" queries. Running detection before the index exists produces candidates that cannot be triaged. The gate costs minutes once; skipping it costs hours repeatedly.*
- **FR-005**: The Orchestrator MUST maintain a configured count of each role and MUST respawn an agent that exits, subject to crash-loop backoff (FR-008).
- **FR-006**: The Orchestrator MUST detect a **dead** agent by absence of heartbeat (see FR-104), not by wall-clock runtime. Wall-clock runtime MAY trigger session rotation per FR-129; it MUST NOT trigger claim reclamation per FR-099. *Rationale: a fixed wall-clock timeout cannot distinguish "hung" from "slow under contention". At scale we observed >90% of fixed-timeout terminations were of healthy agents that were simply waiting on a rate-limited upstream; each false termination discarded in-progress work and re-queued it, producing a treadmill where throughput approached zero. Heartbeat liveness fixes this: an agent that is alive and waiting still heartbeats; an agent that is dead does not.*
- **FR-007**: The Orchestrator MUST support a graceful drain: on shutdown signal, send each agent a wrap-up steer, wait a configurable grace period for natural exit, then terminate.
- **FR-008**: The Orchestrator MUST apply exponential backoff when an agent exits within a short window of being spawned, with a cap on the per-attempt delay but no cap on attempts. *Rationale: linear backoff takes hundreds of attempts to reach a meaningful delay; a multi-hour upstream outage on a multi-agent fleet was observed to produce thousands of stub sessions. Exponential backoff reaches a 30-minute retry interval within ~10 attempts. No attempt cap because outages clear; a fleet that gives up cannot recover unattended.*
- **FR-009**: The Orchestrator MUST expose a status query that reports, for each agent: role, instance index, alive/dead, current claim if any, last heartbeat age, restart count. (US-2)
- **FR-010**: The Orchestrator MUST hot-reload changes to fleet composition (role counts) from configuration without a full restart, reconciling by spawning shortfall and gracefully draining surplus.
- **FR-011**: The Orchestrator SHOULD pre-flight check external dependencies (LLM provider reachable, issue tracker credentials valid, testbed reachable if configured) and report all failures at once rather than failing on the first.
- **FR-012**: The Orchestrator MUST refuse to start a new evaluation run if a previous run hit a hard budget cap and the cap has not been raised, with a message stating which cap and how to reset.
- **FR-013**: The Orchestrator MUST NOT itself perform detection, triage, validation, or reporting. *Rationale: the orchestrator must stay responsive to operator commands and agent lifecycle events. Every time we let it do "just a little" analysis work inline, that work eventually grew until lifecycle handling starved.*

**Functional requirements: conversational.**

- **FR-014**: The Orchestrator MUST answer free-form operator questions about evaluation state, grounded in the actual substrate contents (not the model's general knowledge), citing the records it consulted. (US-3)
- **FR-015**: The Orchestrator MUST accept operator-submitted tasks and place them on the work queue at the operator's chosen priority. (US-12)
- **FR-016**: The Orchestrator MUST watch for operator help requests (issues the operator filed asking the fleet to do something specific) and resolve them: do what is asked, comment with what was done, clear the request marker.
- **FR-017**: The Orchestrator MUST support steering a running agent: deliver an operator message to a specific agent or role, either at the agent's next idle point (non-disruptive) or immediately with interruption (disruptive). *Rationale: "stop what you are doing and look at X" is a different intent from "when you are free, consider X". Supporting only one frustrates the operator.*
- **FR-018**: The Orchestrator SHOULD support an interactive session in which the operator drives a single agent turn by turn with full tool access, for ad-hoc investigation.
- **FR-019**: The Orchestrator's conversational facet MUST NOT modify verdicts, set `exploited`, or mark coverage complete on its own initiative. It may do so on explicit operator instruction, recording the override.
- **FR-020**: Conversational query handling MUST NOT share an execution lane with lifecycle handling: an in-flight LLM-backed answer MUST NOT delay agent respawn, heartbeat checking, status response, or shutdown. *Rationale: lifecycle is deterministic and latency-sensitive; conversational query is model-backed and latency-variable. Running both on the same event loop or thread pool means a slow model turn delays a respawn, which the platform reads as a hung process. The role is one; the execution lanes are two.*

**Orchestrator execution model**: Run the Orchestrator as a persistent service in Kubernetes that the operator connects to for configuration, status, steering, and lifecycle control. Evaluation state MUST remain durable across service restarts and agent supervision MUST follow the heartbeat-based liveness requirements.

**If you omit this role:** you cannot. Something must spawn the fleet and something must answer the operator. **If you split lifecycle from conversational into two roles:** acceptable, and the seed authors ran them that way in production; the seed merges them because to the operator they are one surface, and FR-020 is sufficient to keep the two facets from interfering without a role boundary.

---

### 5.2 Indexer

**Purpose.** Build and maintain the code index: the structural knowledge of the target that every other role queries. Symbols, call graph, file inventory.

**Triggers.** Orchestrator on init; optionally on target change.

**Inputs.** Target source tree.

**Outputs.** Queryable index exposing at minimum: list functions in file, get function body, get callers of function, get callees of function, find symbol by name, full-text search.

**Functional requirements.**

- **FR-021**: The Indexer MUST produce, for every source file in scope, an inventory of defined functions/methods with their location and body. The inventory MUST be produced by a deterministic parser (tree-sitter, ctags, language-server, or equivalent) for every supported language; LLM extraction MAY augment this (e.g., for languages without parser support, or for semantic enrichment) but MUST NOT be the sole source. *Rationale: an LLM-only indexer is the path of least resistance and is fragile — on the seed authors' first from-spec build it returned an empty function table on a real target, and the FR-025 gate released anyway because the query interface was technically satisfied. A deterministic parser underneath is what makes the gate meaningful.*
- **FR-022**: The Indexer MUST produce a call graph (which function calls which) covering at minimum direct static calls.
- **FR-023**: The Indexer SHOULD resolve indirect and dynamic dispatch in the call graph where the target language permits it.
- **FR-024**: The Indexer MUST expose its output through a query interface usable by other roles, supporting at minimum: get-function-body, get-callers, get-callees, find-symbol, full-text search.
- **FR-025**: The Indexer MUST signal "queryable" only when FR-021, FR-022, and FR-024 are satisfied.
- **FR-026**: The Indexer MUST persist its output such that a reader never observes a partially-written or deleted-but-not-yet-rewritten index (see FR-117 for the general atomic-persist rule). *Rationale: a "delete old, write new" persist that crashes between the two steps leaves downstream roles with an empty index and no error. We hit this repeatedly under deploy-time process termination. Write to a new generation, then atomically swap; or write to a staging location, then rename.*
- **FR-027**: The Indexer MUST be incremental on re-run: only changed files are re-parsed; the call graph is patched, not rebuilt. *Rationale: targets of interest are large. Full re-index on every change makes US-11 (re-run after target change) impractical.*
- **FR-028**: The Indexer MUST respect a configured scope (include/exclude path patterns) and MUST NOT index outside it.
- **FR-029**: The Indexer SHOULD degrade gracefully on files it cannot parse (log and skip; do not abort the run).
- **FR-030**: Index construction MUST NOT block the Orchestrator's responsiveness. *Rationale: parsing is CPU-bound. Running it in-process on a cooperative event loop starves health checks and lifecycle handling, which the Orchestrator (or platform) then misreads as a hung process and kills. Offloading to a thread is insufficient when the parser holds a global interpreter lock; a process boundary or a natively-concurrent runtime is required. This is not a theoretical concern: we lost days of compute to index runs being killed at the 80% mark and restarting from zero.*

**Language scope**: The Indexer MUST support Python and Go source in the first build, including the structured code units and location information required by this section. Other source languages are out of scope for the first build.

**If you omit this role:** Detector and Triager lose the ability to ask "who calls this" and "where is this defined", which forces every investigation to grep raw source. Triage quality drops sharply and token cost rises sharply. Not recommended.

---

### 5.3 Cartographer

**Purpose.** Build and maintain the security map: the contextual knowledge of the target that every other role reasons against. Where the Indexer answers "what is the code's structure", the Cartographer answers "what is the code's security posture": what does it expose, where are the trust boundaries, how does data flow, what does an attacker see.

**Triggers.** Orchestrator on fleet spawn (after index gate); operator request; significant target or goals change.

**Inputs.** Index (FR-024); target source; target documentation; testbed description (if any); evaluation goals.

**Outputs.** A set of security-context documents, durable and readable by every role: architecture overview, attack-surface enumeration, trust-boundary map, data-flow description, authentication/authorization model, threat model.

**Functional requirements.**

- **FR-031**: The Cartographer MUST produce an **architecture overview**: the target's major components, their responsibilities, and how they communicate.
- **FR-032**: The Cartographer MUST produce an **attack-surface enumeration**: every entry point reachable by an actor outside the target's trust boundary (network listeners, exposed APIs, CLI surfaces, file inputs, message-queue consumers), with the authentication required at each.
- **FR-033**: The Cartographer MUST produce a **trust-boundary map**: where in the target untrusted input becomes trusted, where one privilege level acts on behalf of another, and what validation (if any) guards each crossing.
- **FR-034**: The Cartographer MUST produce a **data-flow description** for sensitive data classes (credentials, secrets, user data, control commands): where each enters, what it passes through, where it is stored, where it leaves.
- **FR-035**: The Cartographer MUST produce a **threat model** synthesizing FR-031 through FR-034: for each entry point and trust boundary, the attacker positions, attack goals, and threat categories that apply. This MAY be LLM-authored from the preceding documents plus the operator's evaluation goals.
- **FR-036**: The Cartographer's outputs MUST be persisted where every other role can read them and SHOULD be summarizable into a digest small enough to include in another role's prompt context. *Rationale: the security map is most valuable when the Triager can put "this endpoint is unauthenticated and crosses the tenant boundary" directly in front of the model while it is deciding a verdict, not as a document the model might choose to fetch. Front-loading the relevant slice of the map into each downstream role's context measurably improved verdict quality.*
- **FR-037**: Other roles MUST function (at reduced quality) when the security map is absent or partial, and MUST consume whatever portion exists at the time they need it. *Rationale: even with a gate, the map can be incomplete, stale after a target change, or weak on an unfamiliar architecture. Roles that hard-fail without it are brittle; roles that read whatever exists and degrade gracefully are not.*
- **FR-038**: If any of FR-031–FR-035 fails to produce non-empty output, the Cartographer MUST write a minimal fallback for that section consisting of mechanically-derivable facts (file tree, function index from FR-024, configured testbed endpoints) so that downstream roles have something to cite. An empty security map is a Cartographer failure, not graceful degradation. *Rationale: the seed authors' single-pass-giant-prompt approach produced a 0-byte map on every run of the first from-spec build; downstream Detector recall held (the map is not load-bearing for rule-sweep) but the Triager's evidence-gate citations were measurably weaker without it. Chunked or document-per-pass authoring is the recommended shape; the fallback is the floor when authoring fails anyway.*

**Startup decision**: The Cartographer MUST NOT gate fleet startup. Start other agents after the Indexer readiness gate is satisfied, without waiting for the Cartographer or imposing a Triager-only delay. Downstream roles MUST consume the available security-map sections and continue with absent or partial maps as required by FR-037.

**Authoring decision**: Implement the Cartographer as focused passes, one per document type: architecture overview, attack-surface enumeration, trust-boundary map, data-flow description, authentication/authorization model, and threat model. Each pass consumes the source, index, goals, and relevant available preceding outputs. Persist each completed document atomically through the substrate so downstream roles can use it before the entire map is complete. Threat-model synthesis consumes the preceding documents; failed or empty sections MUST receive the mechanically derived fallback required by FR-038.

**If you omit this role:** Triager loses the trust-boundary context that the evidence gate (FR-089) requires it to cite, and falls back to inferring boundaries per finding from raw source, which is slower, costlier, and less consistent. Detector's exploratory mode loses its starting map and converges on obvious surfaces. Reporter's rollup loses its component grouping. The system still functions; every downstream role gets measurably worse. **If you merge it with Indexer:** acceptable on small targets where one agent can do both within the index-gate window; on large targets the merged role either delays the gate or ships an empty map.

---

### 5.4 Detector

**Purpose.** Produce candidate findings. Breadth-first: cover the configured scope using every available technique, queue everything plausible, and let the Triager sort signal from noise.

**Triggers.** Orchestrator on fleet spawn (after index gate); work-queue tasks from Coverage-Guide or operator; optionally on target change.

**Inputs.** Index (FR-024); security map (§5.3); target source; testbed (if any); detection rule corpus; evaluation goals; coverage log.

**Outputs.** Candidate findings written to the finding store (NOT to the issue tracker; see FR-046). Rule-gap records (FR-044).

**Functional requirements.**

- **FR-039**: The Detector MUST support **rule-based code analysis**: for each function in scope, apply each detection rule in the corpus as an LLM-evaluated check that asks whether the function exhibits that rule's vulnerability class, with the function's body and its caller/callee context from the index supplied. *Rationale: function-granularity with call-graph context is the unit at which an LLM can reason about data flow without exhausting context. File-granularity loses the "where does this input come from" signal; line-granularity loses the "what does this function do with it" signal.*
- **FR-040**: The Detector MUST support **dependency scanning**: enumerate third-party dependencies and report those with known published vulnerabilities.
- **FR-041**: The Detector MUST support **secret scanning**: report hardcoded credentials, keys, and tokens in the source tree.
- **FR-042**: The Detector MUST support **exploratory hunting**: an agent instance with the goals, security map, testbed description (if any), and persistent notes in context, free to choose what to investigate, with full read access to source and (where configured) network access to the testbed. *Rationale: rule-based sweeps find what the rules describe. The highest-severity findings in our evaluations were consistently discovered by exploratory agents reasoning about the specific target's design, not by generic rules.*

*Rationale (FR-039 and FR-042 together): the two modes are not alternatives; they are the two halves of a flywheel that, once turning, improves both detection and prevention indefinitely.*

*Rules are systematic and repeatable: every function gets the same check, a rule that fires on one target fires on the next, and the result is reproducible. Exploration is creative and target-specific: an agent reasoning about THIS product's design finds the design-level flaws no generic rule describes, but the result is one-off. Run only rules and you find only what you already knew to look for. Run only exploration and every evaluation starts from zero.*

*The loop runs like this: rules sweep the target; exploratory agents hunt alongside; an exploratory finding is confirmed `true-positive`; the system checks whether any rule would have produced it (FR-044) and, when none would, records a rule gap; an operator (or the Self-Improver extension) generalizes that one finding into a rule, either by revising an existing rule that should have caught it or by authoring a new one; the rule lands in the corpus; the next sweep, on this target and on every future target, catches that entire class systematically. Then exploration finds the next thing the rules miss, and the loop turns again. There is no terminal state: every evaluation enlarges the corpus, and a larger corpus makes the next evaluation's rule sweep catch more on the first pass, freeing exploration to hunt further out. The corpus is the system's accumulated memory of every vulnerability class it has ever seen confirmed.*

*The second half of the flywheel is what makes that accumulation worth the effort: the rule corpus is portable. A rule that detects a vulnerability class in finished code, applied function by function during evaluation, is the same rule that prevents that class in code being written, applied suggestion by suggestion inside an LLM coding assistant. Load the corpus into the developer's editor as the assistant's secure-coding rule set and the bug is caught at the keystroke, not at the audit. So every turn of the loop improves two things at once: the organization's ability to FIND the class (here, in evaluation), and its ability to NOT WRITE the class (everywhere, in development). Detection investment compounds into prevention; prevention shrinks the population the next evaluation has to find. See US-14.*

*The seed authors use CodeGuard, an open-source rule format that predates this seed and was designed independently for exactly this dual deployment (evaluation-time detection and authoring-time prevention from one corpus). Foundry-v2 was built to consume it; the rule-gap loop is Foundry-v2's contribution back. The CodeGuard format is adopted for this build; the rule-gap loop remains required. See the corpus decision below.*

- **FR-043**: The detection rule corpus MUST be a versioned artifact maintained independently of the Detector's agent code, such that rules can be added, revised, audited, and reused across evaluations and outside this system.
- **FR-044**: When a finding produced by exploratory hunting (FR-042) is confirmed `true-positive` and no rule in the corpus would have produced an equivalent candidate, the Triager MUST record a **rule-gap** entry (finding reference, vulnerability class, the pattern that existing rules failed to match) for operator review. *Rationale: this is the mechanism that closes the loop above. Without it, exploratory discoveries stay one-offs and the rule corpus does not improve.*
- **FR-045**: Each candidate finding MUST record at minimum: location (file, function), vulnerability class, a one-paragraph description of why the Detector believes it is a vulnerability, and the technique that produced it (which rule, or "exploratory").
- **FR-046**: The Detector MUST write candidates to the finding store and MUST NOT create issue-tracker issues, send notifications, or otherwise surface candidates to humans. *Rationale: detection is high-volume and low-precision by design. Surfacing every candidate buries the operator. We initially created one issue per detection and produced tens of thousands of issues per target, of which low single-digit percentages survived triage; the issue tracker became unusable. Candidates are internal until the Triager promotes them.*
- **FR-047**: The Detector MUST deduplicate against existing findings by fingerprint (FR-093) before writing a candidate.
- **FR-048**: Exploratory Detector instances (FR-042) MUST consult the coverage log before choosing an area and record what they swept, with what technique, when done. The coverage log is an audit trail, not a stop-list: a prior agent's "swept X, found nothing" entry means "try a different technique on X", not "skip X". *Rationale: without the log, parallel exploratory agents converge on the same obvious surfaces. With the log treated as a stop-list, agents talk each other out of looking at anything ("agent-3 says X is saturated"). The log records attempts, not conclusions.*
- **FR-049**: Exploratory Detector instances MUST NOT treat any prior agent's written claim of "fully covered", "saturated", or "no further work" as authoritative. *Rationale: each agent that wrote such a note had read the previous agent's identical note; citing the count of such notes is circular. The operator decides when detection is done (via Coverage-Guide and yield), not the detectors.*
- **FR-050**: The Detector MUST respect the configured scope (FR-028) and the operator's in-scope/out-of-scope rules (§9).
- **FR-051**: The Detector SHOULD front-load each LLM detection call with the relevant context (function body, callers, callees, security-map excerpt) in the initial prompt rather than relying on the model to fetch it via tools. *Rationale: the first 3-4 tool calls in every investigation were deterministic ("read the function I just told you about"). Pre-fetching them into the first turn cut per-finding cost materially without changing outcomes.*

**Detection scope decision**: Include all four techniques in the first build: rule-based code analysis (FR-039), dependency scanning (FR-040), secret scanning (FR-041), and exploratory hunting (FR-042). Exploratory hunting includes source analysis for every evaluation and live probing only when an authorized testbed is configured, within the operator-defined scope and sandbox controls.

**Rule corpus decision**: Start with CodeGuard and maintain organization-specific additions in a versioned Git repository. Use this organization-wide corpus across evaluations. Each evaluation MUST record the corpus revision used, so rule-based findings can be traced to their evaluated rule content. Changes derived from rule-gap records require operator review before adoption. Configure the corpus repository and pinned revision per evaluation.

**If you omit this role:** there is no system. **If you merge it with Triager:** the merged agent cannot be tuned for recall (Detector's job) and precision (Triager's job) independently; in practice the precision objective wins and coverage suffers. **If you split rule-sweep from exploratory:** acceptable, and the seed authors ran them as separate agent kinds in production; the seed merges them because their outputs and downstream handling are identical.

---

### 5.5 Triager

**Purpose.** Investigate each candidate finding and assign a verdict. The noise filter: most candidates are not real, and the Triager's job is to establish which ones are, with evidence, before any human sees them.

**Triggers.** New candidate in finding store; operator re-triage request; verdict dispute.

**Inputs.** Candidate finding; index; security map (especially trust-boundary map and attack-surface enumeration); target source; testbed (if any); prior verdicts on the same fingerprint.

**Outputs.** Verdict + investigation report written to the finding store; for `true-positive` only, a finding surfaced to Reporter and Validator; no exploitability hint is required.

**Functional requirements.**

- **FR-052**: The Triager MUST assign exactly one verdict from: `true-positive`, `false-positive`, `needs-review`, `not-applicable`, `code-quality`. Definitions in §7.2.
- **FR-053**: The Triager MUST conduct an investigation before assigning a verdict, using at minimum: read the implicated code, trace the data flow from entry point to sink using the index, identify any sanitization or validation on the path, locate the entry point and trust boundary in the security map, and assess whether the entry point is reachable by an attacker.
- **FR-054**: The Triager MUST NOT assign `true-positive` unless the **evidence gate** (§7.3) is satisfied (US-7): the investigation report cites specific code locations establishing (a) reachability from an attacker-controlled entry point, (b) crossing of a trust boundary, and (c) a concrete security impact; and every cited location resolves to real code on disk. *Rationale: an LLM asked "is this a vulnerability" will often say yes with a fluent, plausible, fabricated justification. Requiring structural evidence with citations that are mechanically verified to exist makes fabrication detectable: a hallucinated function name fails the resolve check. This single gate moved our true-positive precision from "unusable" to "reviewer trusts the label". The model is not permitted to award itself `true-positive`; the gate does.*
- **FR-055**: A candidate that fails the evidence gate but that the Triager believes is likely real MUST be assigned `needs-review`, not `true-positive`. *Rationale: `needs-review` is the honest verdict for "I think so but cannot prove it". Conflating it with `true-positive` destroys the value of the `true-positive` label.*
- **FR-056**: The Triager MUST record its full reasoning alongside the verdict. A verdict without an investigation report MUST be rejected by the finding store. *Rationale: a bare `true-positive` label is an unverifiable model assertion. The reasoning is what a reviewer audits; the label is just an index into it.*
- **FR-057**: The Triager MUST short-circuit candidates whose location is outside the configured scope to `not-applicable` without investigation.
- **FR-058**: The Triager SHOULD consult the testbed during investigation when one is configured and the candidate's exploitability is uncertain from code alone.
- **FR-059**: The Triager MUST surface a finding to humans (via Reporter) only on `true-positive`. Other verdicts are recorded in the finding store and visible via dashboard/Orchestrator but do not generate issues. `needs-review` MUST remain internal and MUST NOT create GitHub issues or publication notifications; it remains available through the dashboard and operator queries.
- **FR-060**: The Triager SHOULD check whether a fingerprint-equivalent finding was already triaged in a related prior evaluation and, if so, inherit non-`true-positive` verdicts and use prior `true-positive` verdicts as investigation priors rather than conclusions. *Rationale: re-investigating known false positives across re-runs is pure waste. Re-investigating known true positives is sometimes warranted (deployment context differs) and sometimes not; this is configurable.*
- **FR-061**: The Triager MUST be idempotent: re-triaging a candidate replaces the prior verdict; it does not create a duplicate finding.

**Investigation decision**: The Triager uses an open-ended tool-use loop guided by a fixed investigation checklist. The checklist MUST cover the evidence required by FR-053 and FR-054 and §7.3; the agent may pursue additional investigative steps within the configured scope and budget. Record the checks performed, supporting code citations, and reasons for the final verdict. Checklist completion or model confidence alone MUST NOT qualify a finding as `true-positive` without the required verified evidence.

**If you omit this role:** every Detector candidate reaches a human. At observed candidate volumes this is not a usable system. **If you merge it with Validator:** triage becomes gated on testbed availability and testbed throughput, which is typically the slowest stage; the candidate backlog grows unboundedly.

---

### 5.6 Validator

**Purpose.** For every finding the Triager marked `true-positive` where a testbed is configured, independently attempt to reproduce the headline impact against the testbed. The proof filter: "exploited" means demonstrated, not argued.

**Triggers.** Every new `true-positive` finding; operator request. An exploitability hint affects priority only.

**Inputs.** Finding with Triager's investigation report; testbed; target source; index.

**Outputs.** `exploited` flag set or cleared on the finding, with a runnable proof-of-concept artifact on success or a written explanation on failure.

**Functional requirements.**

- **FR-062**: For every `true-positive` finding, where a testbed is configured, the Validator MUST attempt to reproduce the finding's stated impact against the testbed and MUST do so as an independent check: a fresh agent instance, with the finding report and PoC artifact as input, that does not share conversational state with the agent that produced them. The Validator MUST NOT be gated on a Triager-set "exploitability" hint; that hint MAY raise priority but MUST NOT be a precondition. *Rationale: an agent grading its own exploit will rationalize partial success as success. A clean-room checker that receives only the artifact and the claimed impact, runs the artifact, and reports whether the impact was observed, cannot. Gating on a Triager-set exploitability flag means a miscalibrated or degraded Triager silently disables the Validator; on the seed authors' first from-spec build it never ran once.*
- **FR-063**: The Validator MUST set `exploited` only if the headline impact was directly observed on the live testbed. The following are NOT `exploited`: payload accepted but downstream effect not observed; sink reached via debugger manipulation rather than the attack path; vulnerable branch reached but final step deliberately not triggered; any reproduction in the absence of a testbed. *Rationale: "exploited" is the label reviewers will sort by first (US-8). Every dilution of its meaning ("would be exploitable if", "exploited a similar issue") destroyed reviewer trust in it. The bar is binary and high.*
- **FR-064**: On reproduction failure, the Validator MUST record a structured explanation (what was attempted, what was observed, why it differs from the claim) and MUST NOT clear the `true-positive` verdict. *Rationale: failure to reproduce on a particular testbed on a particular day does not mean the vulnerability is not real.*
- **FR-065**: The Validator MUST produce a self-contained, runnable proof-of-concept artifact on success, with setup prerequisites documented in the artifact header. (US-10) The artifact demonstrates the exploit; it is not a regression test for the fix. The artifact header MUST include the notice "Authorized testing only" in addition to setup prerequisites. No additional license or data-classification notice is required by this first-build specification.
- **FR-066**: The Validator MUST operate within the sandbox (§9) and MUST honor the operator's hard rules (out-of-scope hosts, prohibited actions). A reproduction that would require violating a hard rule is recorded as not-exploited with that reason.
- **FR-067**: The Validator SHOULD limit reproduction attempts per finding (a small fixed number) before recording not-exploited. *Rationale: unbounded retry on a finding that is not actually exploitable consumes testbed time that other findings need.*
- **FR-068**: When no testbed is configured, the Validator MUST degrade to producing the PoC artifact without running it, MUST NOT set `exploited`, and MUST record "no testbed" as the reason.

**Testbed decision**: Testbeds are optional and available for some evaluations. Retain the Validator as a distinct core role. With a configured testbed, independently attempt live reproduction per FR-062 and FR-063; without one, follow FR-068 and never set `exploited`.

**If you omit this role:** the system cannot distinguish "argued from code" from "demonstrated on a running system". For some organizations that distinction does not matter; for most reviewers it is the first filter they apply.

---

### 5.7 Coverage-Guide

**Purpose.** Translate the operator's stated evaluation goals into a finite checklist, steer the fleet toward uncovered items, judge when each item has been credibly attempted, and declare coverage complete. Half of the "done" signal.

**Triggers.** Orchestrator on fleet spawn; periodic review cycle; operator goal change.

**Inputs.** Evaluation goals; security map (architecture and attack surface, for grounding goals in real components); coverage log (FR-048); finding store; work-queue history.

**Outputs.** Coverage checklist (internal); coverage-complete flag (consumed by budget governor); coverage report (human-facing, via Reporter); directed tasks queued for Detector.

**Functional requirements.**

- **FR-069**: The Coverage-Guide MUST, on first run, derive a finite checklist of (component × goal) coverage items from the evaluation goals and security map, where each item has a stated bar for what "credibly attempted" means.
- **FR-070**: The Coverage-Guide MUST NOT invent goals; if the evaluation goals document is empty or template placeholder text, it waits and re-checks rather than proceeding. *Rationale: an LLM handed an empty goals file will helpfully synthesize plausible goals and then declare them covered. The operator's stated goals are the only authority for what "done" means (Constitution X).*
- **FR-071**: The Coverage-Guide MUST, on each review cycle, gather evidence for each open checklist item from the coverage log, finding store, and work-queue history, and check off items where the bar is met. "We swept X for Y and found nothing" satisfies "X: Y" exactly as well as "we swept X for Y and filed three findings". Coverage measures attempt, not outcome.
- **FR-072**: The Coverage-Guide MUST queue directed tasks on the work queue for checklist items with no matching activity, phrased so a Detector instance with no other context can act on them. *Rationale: without directed tasks, uncovered items stay uncovered until an exploratory agent stumbles onto them; the Coverage-Guide is the only role with the gap view, so it is the role that must close it.*
- **FR-073**: The Coverage-Guide MUST set the coverage-complete flag only when every checklist item is closed, and MUST clear it if the operator changes the goals.
- **FR-074**: The Coverage-Guide MUST NOT itself detect, triage, validate, or close work-queue tasks it queued. It reads, judges, and steers. *Rationale: the role that decides whether work is done must not also be the role that does the work; a Coverage-Guide that can close its own tasks will, under pressure to reach coverage-complete, do exactly that.*
- **FR-075**: The Coverage-Guide SHOULD record an estimate of remaining work each cycle, with a one-line basis, for the operator's planning.
- **FR-076**: The Coverage-Guide MUST persist its checklist across restarts, atomically per FR-117, without rebuilding it from scratch on each wake. *Rationale: rebuilding loses check-off history and causes already-covered items to be re-queued; a half-written checklist after a crash has the same effect.*

**If you omit this role:** the system has no "done" signal beyond budget exhaustion or operator judgment. The yield auto-stop (§9) will fire on the first dry spell regardless of whether the stated goals were attempted. For unbounded "run until I stop you" evaluations this is acceptable; for "evaluate this product by Friday" it is not.

---

### 5.8 Reporter

**Purpose.** Produce the human-facing output: a self-contained writeup for each confirmed finding, severity and weakness classification for each, and an evaluation-level rollup that a reviewer can act on.

**Triggers.** New `true-positive` finding; `exploited` flag set or cleared; coverage-complete flag set; periodic rollup refresh.

**Inputs.** Finding store; index; security map; coverage checklist and report; evaluation goals.

**Outputs.** Per-finding reports published to the issue tracker; evaluation rollup document.

**Functional requirements.**

- **FR-077**: For each `true-positive` finding, the Reporter MUST produce a self-contained report (US-10) including: title, affected component and location, description of the vulnerability, attacker prerequisites, impact statement, reproduction steps, the Triager's evidence, and (if `exploited`) a reference to the PoC artifact.
- **FR-078**: The Reporter MUST assign each `true-positive` finding a weakness classification. Use CWE as the weakness taxonomy. Include the CWE ID, name, and a brief mapping rationale supported by the finding evidence. The mapping MUST describe the demonstrated weakness rather than an unsupported inference.
- **FR-079**: The Reporter MUST assign each `true-positive` finding a severity. Use CVSS 4.0. Each report MUST include the numeric score and complete CVSS 4.0 vector used to compute it, together with an evidence-supported rationale for the assigned metrics. Validate that the vector is well-formed and the reported score matches its calculation.
- **FR-080**: The Reporter MUST publish each finding report to the issue tracker as exactly one issue, with labels encoding at minimum: source (this system), verdict, severity, exploited yes/no. *Rationale: labels are how reviewers and downstream tooling filter. A consistent, minimal label taxonomy is more useful than a rich, inconsistently-applied one.*
- **FR-081**: The Reporter MUST NOT publish a finding whose verdict is anything other than `true-positive` (per FR-059).
- **FR-082**: The Reporter MUST update, not duplicate, the issue for a finding whose report changes (severity revised, exploited flag set, evidence added).
- **FR-083**: The Reporter MUST produce an evaluation-level rollup (US-9) containing at minimum: finding count by severity and by exploited status; findings grouped by owning component (per the security map's architecture overview); coverage status against each stated goal with what was attempted and what was found. *Rationale: a flat list of findings, however well each is written, does not answer the reviewer's first question, which is "where do I start". Grouping by component answers "who owns this"; severity × exploited answers "what is on fire".*
- **FR-084**: The rollup SHOULD prioritize findings using their reported severity and independently demonstrated exploitation. It MUST NOT claim verified attack chains or keystone fixes without supporting evidence; attack-chain mapping is out of scope for this build.
- **FR-085**: Finding reports MUST NOT name the LLM model or provider, the system's internal agent identifiers, or internal hostnames. *Rationale: reports are forwarded outside the operating team. Internal implementation details leak operational information and date the report.*
- **FR-086**: Every code location referenced in a report MUST be a permalink that resolves for the report's reader. *Rationale: a reference to "line 47" is wrong the moment the file changes. A reference to a commit-pinned location is durable.* Source permalinks MUST use https://github.com/{owner}/{repo}/blob/{commit}/{path}#L{line}, with the full evaluated commit SHA and URL-encoded path. Before sharing reports, the operator MUST grant intended readers access to both the source repository at the evaluated revision and the reporting repository. Foundry-v2 MUST NOT automatically grant repository permissions; source links MUST use the pinned evaluated commit.

**Publication destination decision**: GitHub Issues is the only external finding-publication destination for the first build. Export to additional defect trackers, vulnerability-management systems, or ticketing systems is out of scope. Internal finding storage, dashboard visibility, and report artifacts remain required.

**If you omit this role:** findings exist only in the internal store. Something must render them for humans. **If you fold severity/classification (FR-078, FR-079) out into its own role:** acceptable; the seed authors ran it both ways. Folding it in is simpler.

---

## 6. Extension Roles

The first build implements the eight core roles only. Deep-Tester, Variant-Hunter, Attack-Mapper, Remediator, and Self-Improver are out of scope for this build and deferred for reconsideration after the core pipeline produces trustworthy findings.

---

## 7. Finding Lifecycle

### 7.1 States

```
  ┌──────────┐  triage  ┌────────────────┐
  │candidate ├─────────►│ verdict        │
  └──────────┘          │ assigned       │
                        └───┬─────────┬──┘
                            │ TP      │ FP / NA / CQ / NR
                            ▼         ▼
                     ┌───────────┐ ┌──────────┐
                     │ confirmed │ │ recorded │ (internal only)
                     └─────┬─────┘ └──────────┘
                           │ validate (if testbed configured)
                           ▼
              ┌───────────────────────┐
              │ confirmed [exploited?]│
              └───────────┬───────────┘
                          │ report
                          ▼
                   ┌─────────────┐
                   │  published  │
                   └─────────────┘
```

### 7.2 Verdicts

| Verdict | Meaning | Surfaced to humans? |
|---|---|---|
| `true-positive` | A real vulnerability, with evidence satisfying §7.3. | Yes (FR-059) |
| `false-positive` | Investigated; not a vulnerability. Reasoning recorded. | No |
| `needs-review` | Likely real but evidence gate not satisfied; or genuinely ambiguous. | Internal dashboard and operator queries only; no GitHub issue |
| `not-applicable` | Out of configured scope, or in test/example/generated code. | No |
| `code-quality` | A real defect but not a security vulnerability (correctness, maintainability). | No |

- **FR-087**: Every finding MUST carry exactly one verdict once triaged. Verdicts are mutable (re-triage replaces).
- **FR-088**: The finding store MUST retain `false-positive`, `not-applicable`, and `code-quality` findings with their reasoning. *Rationale: "we already looked at this and here is why it is not a bug" is valuable on re-run (FR-060) and when a reviewer asks "did you consider X" (FR-014).*

### 7.3 Evidence gate

- **FR-089**: A `true-positive` verdict MUST be accompanied by an investigation report containing at least one cited code location for each of: (a) **reachability**: an attacker-controlled entry point from which the vulnerable sink is reachable; (b) **trust boundary**: the point at which untrusted data crosses into trusted processing without sufficient validation; (c) **impact**: the concrete security consequence at the sink.
- **FR-090**: For vulnerability classes where **presence is the vulnerability** — a hard-coded credential, key, or token in source (CWE-798/259/321); use of a cryptographic primitive deprecated for the cited purpose (CWE-327); a sensitive value committed to the repository — the FR-089 trust-boundary leg MAY be satisfied by the citation "the source repository itself" and the reachability leg by the file's inclusion in the build. The impact leg MUST still be cited (what the credential/key/value grants access to). *Rationale: a credential in source is exposed to anyone with repository read access regardless of code-path reachability; demanding a call-graph reachability proof for it produces `needs-review` on findings that are unambiguously real. This carve-out is narrow and enumerated; it does NOT apply to data-flow classes (injection, IDOR, SSRF, traversal), where the three-leg gate remains the floor — the gate already passes unsound arguments on those (it checks that citations resolve, not that the argument is valid), and weakening it further is the wrong direction.*
- **FR-091**: Every cited code location in FR-089 MUST be mechanically verified to resolve to real code in the target at verdict time. A citation that does not resolve demotes the verdict to `needs-review`.

*Rationale: this is the single most important quality control in the system. An LLM will produce confident, fluent, wrong vulnerability claims. The gate does not ask the model to be more careful; it requires the model's claim to be checkable, and checks it. The three legs are chosen because together they constitute the minimum argument that something is exploitable; a finding missing any one of them is at best a lead. The Cartographer's trust-boundary map (FR-033) is what makes leg (b) tractable: without it, every triage independently re-derives where the boundaries are.*

### 7.4 Exploited

- **FR-092**: `exploited` is a flag on a `true-positive` finding, set only by the Validator per FR-062 and FR-063, never by Detector, Triager, or Reporter, and never inferred.

### 7.5 Fingerprint

- **FR-093**: A finding's fingerprint MUST be a deterministic hash of (normalized file path, function/symbol name, vulnerability class). It MUST NOT include line numbers, code snippets, or detection timestamps. *Rationale: the fingerprint's job is to recognize "the same finding" across re-runs after the target has changed. Line numbers and snippets change on any nearby edit, causing every re-run to re-file everything as new. Path + symbol + class is stable across edits to the function body and breaks only when the function moves or is renamed, which is the correct point to treat it as new.*
- **FR-094**: Deduplication (FR-047, FR-060, FR-082) MUST key on fingerprint.

### 7.6 Label taxonomy

- **FR-095**: Published findings MUST carry a minimal, fixed label set encoding: source-system marker, verdict, severity tier, exploited yes/no, weakness class. The system MUST create missing labels on first use rather than fail.
- **FR-096**: The system SHOULD use one transient "in-progress" label that any role adds while holding a finding's claim and removes on release, layered over (not replacing) the verdict label.

**GitHub label mapping decision**: Use the following fixed names and six-digit hexadecimal colors. Expand slash-separated alternatives into individual labels.

| Meaning | Label | Color |
|---|---|---|
| Source system | `foundry-v2` | `5319E7` |
| Published verdict | `verdict:true-positive` | `0E8A16` |
| Critical severity | `severity:critical` | `B60205` |
| High severity | `severity:high` | `D93F0B` |
| Medium severity | `severity:medium` | `FBCA04` |
| Low severity | `severity:low` | `0E8A16` |
| No severity | `severity:none` | `CFD3D7` |
| Exploited | `exploited:yes` | `B60205` |
| Not exploited | `exploited:no` | `CFD3D7` |
| Weakness | `cwe:<ID>` (for example, `cwe:79`) | `1D76DB` |
| Active claim | `in-progress` | `FBCA04` |

Create missing labels per FR-095. Derive the severity tier from the report's CVSS 4.0 score: none = 0.0, low = 0.1–3.9, medium = 4.0–6.9, high = 7.0–8.9, critical = 9.0–10.0. See the [FIRST CVSS 4.0 specification](https://www.first.org/cvss/v4.0/specification-document). Published issues have exactly one current verdict label, one severity label, and one exploitation label, plus the source marker and applicable CWE label. Replace superseded labels when findings change. The transient `in-progress` label follows FR-096.

---

## 8. Coordination Substrate

The substrate is specified as **behavior**, not mechanism. Whether it is a database, a directory of files, or a message bus is an §11 decision.

### 8.1 Work queue

- **FR-097**: The work queue MUST provide ordered tasks with at minimum: stable id, title, free-text description, priority position, state (`open` / `blocked` / `closed`). The substrate SHOULD support multiple named queues sharing identical claim/auto-block/stable-id semantics. *Rationale: the work queue, the coverage log (FR-048), the Coverage-Guide's checklist (FR-069/074), and per-finding handoff checklists are, in the reference implementation, named instances of one mechanism rather than four separate components. Specifying them as one mechanism with one set of guarantees is simpler to build and harder to get wrong.*
- **FR-098**: Claiming MUST be atomic: two agents claiming concurrently MUST receive different tasks (or one receives "none available").
- **FR-099**: A claim MUST be tied to the holder's liveness such that the claim is automatically released within bounded time of holder death, with no operator intervention. *Rationale: without this, every crashed agent permanently strands whatever it held. We tried "operator manually unlocks" and "next agent breaks the lock if it looks stale"; both produced either stranded work or duplicate work. Liveness-tied release is the only mechanism that produced neither.*
- **FR-100**: A task that has been claimed and released N times without completion (N small and operator-configurable) MUST auto-transition to `blocked`. *Rationale: a task several agents have given up on is probably a dead end as written. Auto-block stops the fleet grinding on it; an operator or the Coverage-Guide can re-open it with a better description. The seed authors used N=3.*
- **FR-101**: The queue MUST be operator- and agent-writable (add, edit, reprioritize, close) at runtime.
- **FR-102**: An agent that discovers follow-on work outside the scope of its current claim SHOULD queue it as a new task rather than pursue it inline or steer a peer toward it (FR-106). An agent that learns something that improves an existing task's description SHOULD edit that task in place. *Rationale: the queue is the fleet's pull-based coordination primitive. Queueing a lead lets the next idle agent claim it on its own terms; chasing it inline derails the held task; peer-steering interrupts a busy agent and overrides its judgment, which is the agent-consensus failure Constitution X guards against. The seed authors found that exploratory agents instructed "add it, don't chase it" produced better depth on the held task and better breadth across the fleet, and that agent-edited task descriptions compounded context across claimants.*
- **FR-103**: Task ids MUST be stable and distinct from priority positions. *Rationale: positions shift as tasks are inserted and closed; an agent that recorded "I am working position 3" is working a different task a minute later.*

### 8.2 Liveness

- **FR-104**: Every agent MUST emit a heartbeat at a fixed short interval to a location the Orchestrator and the claim mechanism observe. Liveness is defined as "heartbeat age below threshold". Wall-clock runtime is NOT a liveness signal.
- **FR-105**: Heartbeat emission MUST NOT be blocked by the agent's primary work. *Rationale: an agent whose heartbeat shares an event loop or thread pool with CPU-bound or upstream-blocked work will miss beats while perfectly healthy, and be killed for it. The heartbeat must have its own execution lane.*

### 8.3 Inter-agent communication

- **FR-106**: Agents MAY send messages to peers. A peer message MUST be delivered as advisory, prefixed to distinguish it from operator instruction, and the recipient MUST treat it as a hint, not a command. *Rationale: agents are sometimes wrong. An agent that obeys peer messages can be steered into abandoning correct work by a peer's mistake. The operator's instructions outrank anything any agent wrote anywhere.*
- **FR-107**: Agents MUST be able to post an asynchronous **operator message**: a short, one-way note surfaced to the operator, tagged with the originating agent and a kind drawn from at minimum {`blocker`, `request`, `feedback`, `info`}. The agent MUST NOT block awaiting a reply. *Rationale: an agent that hits a human-only blocker (testbed down, tool missing, sandbox too tight, scope ambiguous) otherwise has nowhere to put that except a log line. US-2 requires the operator to see what agents are blocked on; this is the channel that carries it. One-way because a fleet that pauses for human answers is a fleet that mostly pauses.*
- **FR-108**: Operator messages MUST be deduplicated across the fleet before surfacing: when a new message is substantively equivalent to a recent unacknowledged one, it is suppressed and the existing message's id is returned to the posting agent. *Rationale: N parallel agents discover the same environmental problem N times. The operator needs to hear it once.*
- **FR-109**: The operator MUST be able to acknowledge an operator message (removing it from the unacked view and from the dedup pool) and SHOULD be able to reply, where a reply is delivered as an FR-017 steer to the originating agent.
- **FR-110**: Agents MUST NOT use operator messages for progress narration, finding-specific details, or questions the agent can answer from the substrate. *Rationale: same discipline as FR-111/FR-114 — the channel's value is its signal-to-noise ratio.*
- **FR-111**: Agents SHOULD NOT use peer messages for status updates or work delegation; the work queue (FR-101, FR-102) and claim state already encode those.

### 8.4 Shared notes

- **FR-112**: The fleet MAY maintain a shared persistent-notes document that fresh agent instances read at startup, containing high-value cross-cutting facts (secret references, environment gotchas, architectural cribs; never credential values).
- **FR-113**: Where a shared-notes document exists, it MUST be size-bounded and lock-protected for writes.
- **FR-114**: The shared-notes document MUST NOT contain coverage claims, finding-specific details, or "X is done" assertions. *Rationale: notes are read by every fresh agent as near-authoritative context; a "done" assertion here is exactly the agent-consensus failure Constitution X prohibits.*

### 8.5 Rate governance

- **FR-115**: The system MUST NOT impose internal rate caps below the upstream provider's actual limit. The provider is the rate arbiter; the system's job is to handle the provider's backpressure signals (HTTP 429, quota errors), not to pre-throttle. *Rationale: every internal cap we set was wrong in one direction or the other within a week, either leaving paid-for capacity idle or doing nothing because the real limit was lower. Adaptive backoff against the provider's actual signal converges on the real limit without configuration.*
- **FR-116**: Backoff on provider rate-limit MUST be shared across all agents calling that provider, not per-agent. *Rationale: per-agent backoff means N agents independently rediscover the same limit N times; shared backoff means one agent's 429 informs all of them.*

### 8.6 Atomic persistence

- **FR-117**: Every persisted artifact that more than one component reads — the index, the finding store, the coverage checklist, the shared-notes document — MUST be updated by writing the new state completely and then atomically replacing the old, never by deleting the old and then writing the new. *Rationale: "delete old, write new" with a crash between the steps leaves every reader with nothing and no error. This is the general rule of which FR-026 (index) and FR-076 (checklist) are instances. See Constitution XI.*

---

## 9. Governance & Safety

### 9.1 Sandbox

- **FR-118**: The agent fleet MUST run inside an isolation boundary (US-6) that constrains network egress to an operator-configured allowlist (the LLM provider, the issue tracker, the testbed, and nothing else by default) and that an agent with full privileges inside the boundary cannot bypass. *Rationale: an exploratory agent with network access and instructions to "find vulnerabilities" will, eventually, probe something it should not. The constraint must be enforced by infrastructure, not by prompt; an agent that has been prompt-injected by content in the target will not honor prompt-level rules.*
- **FR-119**: The sandbox MUST mount the target source, the agent configuration, the agent prompts, and the sandbox's own definition as read-only to the agents.
- **FR-120**: The operator MUST be informed at setup time that allowlisted destinations are pivot points: an agent that can reach the testbed can reach whatever the testbed can reach; an agent that can reach the issue tracker can post content a human will read. The sandbox bounds blast radius; it does not eliminate it.

**Network enforcement decision**: Enforce the authorized destination allowlist using Kubernetes NetworkPolicies backed by a network plugin that enforces those policies. Evaluation workloads MUST have default-deny egress, with explicit allowances only for operator-authorized target, testbed, and infrastructure destinations. Enforcement MUST satisfy FR-118 and Constitution IX, including when an agent has root inside its workload. Policy installation and an independent connectivity check MUST succeed before agents start; if enforcement cannot be verified, the evaluation MUST NOT start. **Network plugin decision**: Cilium is the cluster network plugin responsible for enforcing the selected NetworkPolicies. **Destination mapping decision**: Use explicit IP/CIDR allowlist entries maintained by the operator, with approved destination ports and protocols. The operator supplies and updates the entries for GitHub, the separate Ollama GPU server, authorized testbeds, and required infrastructure. Runtime policy MUST enforce only the configured entries; DNS resolution MUST NOT automatically expand the allowlist. Address changes require an operator-approved configuration update and connectivity verification before affected access resumes.

### 9.2 Scope rules

- **FR-121**: The configuration MUST support an operator-authored hard-rules block, delivered to every agent in its system prompt, stating in plain language what the agent must never do (out-of-scope hosts, prohibited actions, data it must not modify). This is defense-in-depth behind the sandbox, not a substitute for it.
- **FR-122**: When operating against any system that is not a disposable testbed, the default hard rules MUST prohibit at minimum: denial of service, data deletion or modification, credential changes, actions affecting users other than designated test users.

### 9.3 Budget

- **FR-123**: The Orchestrator MUST track cumulative LLM spend (in currency) and cumulative wall-clock runtime across all runs of an evaluation, halting the fleet when either exceeds an operator-set cap. (US-5)
- **FR-124**: Spend tracking MUST account for every model call by every role. Where the provider does not report cost directly, the system MUST estimate from token counts and configured rates, and MUST surface what fraction of the reported total is estimated.
- **FR-125**: Budget caps default to unset (unlimited). The pre-flight check (FR-011) SHOULD warn when both are unset.

### 9.4 Yield auto-stop

- **FR-126**: The system MUST compute trailing yield: confirmed findings, weighted by severity and by `exploited` status, divided by spend, over a trailing spend window.
- **FR-127**: The Orchestrator MUST halt the fleet when trailing yield falls below an operator-set threshold (US-4), but ONLY when all of: (a) at least one full trailing window of spend has accumulated; (b) a configured minimum runtime has elapsed; (c) the coverage-complete flag is set (FR-073). *Rationale: each precondition guards a real failure. Without (a) the metric is noise. Without (b) an early dry spell kills a young evaluation. Without (c) "we found nothing in the first six hours" stops the run before the required ground was covered.*
- **FR-128**: Severity weights, the exploited multiplier, the trailing window size, the minimum runtime, and the threshold MUST be operator-configurable. The seed does not prescribe values. *Rationale: "at what return is this no longer worth the compute" is an organization-specific judgment, so the threshold is not prescribed. The shape of the severity weights is not arbitrary, though: the metric's job is to approximate economic value delivered per unit spend, so weights should track the relative real-world value of findings at each tier. A roughly geometric scale (constant ratio between adjacent tiers) does this and has two further properties a linear scale lacks: the trailing yield is dominated by the highest-severity finding in the window rather than by low-severity volume, and the threshold means the same thing across evaluations of very different targets. The seed authors used ~3.15× per tier (≈√10), calibrated against multi-year bug-bounty payout ratios, with a 2× multiplier for `exploited` findings to reflect the higher reviewer trust Constitution VII attaches to that flag. Builders SHOULD start geometric and tune the ratio to their own value data; builders SHOULD NOT default to a linear scale.*

### 9.5 Agent lifecycle limits

- **FR-129**: Each role's instances SHOULD have a configurable soft session limit after which the agent is steered to wrap up and release its claims, and a hard limit after which the Orchestrator terminates the process and spawns a fresh instance in the slot. The limit MAY be measured in wall-clock time, turns, or tokens. This is session rotation, not liveness detection: the Orchestrator MUST NOT reclaim or re-queue the rotated agent's held work on the hard limit (Constitution III); the soft steer exists precisely so the agent releases it first. *Rationale: long sessions accumulate context that crowds out reasoning, and exploratory agents (FR-042) burn spend on unproductive rabbit holes while remaining perfectly alive. A fresh session with persistent notes outperforms a stale one. The soft limit gives the agent time to hand off cleanly; the hard limit caps the cost of one that doesn't. The seed authors used wall-clock (150 min soft / +15 min hard) for exploratory roles.*
- **FR-130**: An agent that has genuinely run out of useful work MAY retire itself; the Orchestrator spawns a fresh instance in the slot.
- **FR-131**: Agents MUST NOT invent busywork to avoid retirement.

---


### 9.6 Local inference accounting and execution safeguards

- **FR-132**: For self-hosted Ollama, the operator MUST configure estimated input/output token rates in a named currency when spend-based yield auto-stop is enabled. Rates and the yield spend window MUST be positive; absent or zero rates MUST NOT be treated as free inference or permit division by zero. If yield auto-stop is explicitly disabled, report yield as unavailable while retaining runtime caps and operator stop. No monetary rates are invented by the system.
- **FR-133**: Each completed model call MUST contribute its token usage exactly once to the durable budget ledger. Interrupted calls with unknown usage MUST be marked unknown, make spend/yield incomplete, and disable spend-derived automatic completion until reconciled; runtime caps continue to apply. The dashboard MUST distinguish estimated, known, and incomplete accounting.
- **FR-134**: Before spawning agents, the Orchestrator MUST verify the configured Ollama endpoint/model can execute a representative tool call, return a system-prompt-conditioned answer, and expose usable token counts. Failure MUST identify the missing capability and prevent startup; model quality acceptance remains separate from protocol compatibility.
- **FR-135**: Evaluation workloads MUST be unable to alter namespace policy, obtain host privileges, mount arbitrary host paths, or use cluster credentials to escape the sandbox. Container-root access does not authorize privileged pods or host networking. Only operator-controlled infrastructure identities may install policy; preflight MUST verify denied egress and writes remain denied from the agent environment.
- **FR-136**: Only authenticated, operator-authorized callers may start, stop, steer, change configuration, or query the Orchestrator web interface. Agent identities may use only the substrate operations allowed for their role and evaluation; target content cannot authenticate as an operator. Planning MUST integrate this access contract with the cluster's existing operator access mechanism.
- **FR-137**: Reporter retries and concurrent instances MUST converge on one GitHub issue per fingerprint, including when issue creation succeeds but the response is lost. Persist publication intent and reconcile by stable identity before retrying creation. A revised non-true-positive verdict MUST update the existing issue to withdraw the confirmed claim and remove stale confirmation labels without creating a replacement issue.
- **FR-138**: Enforce one active evaluation per Foundry-v2 installation atomically across service restarts and concurrent start requests. Only one substrate instance may open the SQLite files; startup MUST prevent overlapping owners. Checkpoints and committed data MUST survive owner replacement without partially visible state.

**Runtime parameters.** Operator configuration defines heartbeat period, stale threshold, monitoring/claim cycle, drain grace, provider backoff bounds, retry block threshold, validation attempt limit, session limits, and yield window/weights/threshold/minimum runtime. Validate positive durations and bounds, stale threshold greater than heartbeat period, and hard session limit greater than soft limit. Omitted required values are reported by configuration validation, not silently guessed. Stale claims are reclaimed by the first monitoring cycle after their heartbeat threshold is exceeded. Provider backpressure includes explicit overload responses from self-hosted inference; adaptive retry MUST NOT silently become a permanent capacity cap. No payment API is assumed.

## 10. Observability

- **FR-139**: The system MUST provide an operator dashboard (US-2) showing at minimum: per-agent state (role, index, alive, current claim, heartbeat age); finding counts by verdict, severity, exploited; coverage checklist state; budget consumed against caps; trailing yield against threshold; work-queue depth; unacknowledged operator messages by kind, with `blocker` visually distinguished.
- **FR-140**: The system MUST provide a merged live activity feed across all agents, filterable by role and by event kind.
- **FR-141**: The system MUST log every agent session in a structured, replayable format (turns, tool calls, tool results, token usage) to durable storage.
- **FR-142**: The system SHOULD provide a per-role cost and token rollup, and a tool-usage histogram, sufficient for an operator (or the Self-Improver extension) to identify where spend is going.
- **FR-143**: The status query (FR-009) and dashboard MUST agree with each other and with the substrate's actual contents. *Rationale: a dashboard that reads stale or differently-computed state from the source of truth produces operator decisions based on fiction. We shipped this bug more than once.*
- **FR-144**: The system MUST surface its own degraded states (provider unreachable, index incomplete, sandbox misconfigured, abnormal error rate) on the dashboard prominently, not only in logs.

**Dashboard delivery decision**: Deliver the dashboard as a web UI served by the persistent Orchestrator service. It MUST display the fleet, findings, coverage, budget, and status information required by this section, including internal findings available to the operator. Dashboard data MUST come from the authoritative persisted substrate state and agree with Orchestrator status queries per SC-008.

---

## 11. Integration Surfaces

Each subsection below defines the **interface contract** a Foundry-v2 implementation needs from an external system, followed by the selected concrete integration. The seed authors' own choice is noted as one worked example, not a recommendation. The roles in §5 depend only on these contracts, never on a concrete provider, so any system satisfying a contract can be substituted without redesigning a role (US-13).

### 11.1 Version control & issue tracker

**Contract:** read access to target source at a pinned revision; create/read/update/label issues; comment on issues; resolve a (file, revision, line) tuple to a human-navigable permalink.

**Integration decision**: Use GitHub repositories for target source and GitHub Issues for published findings. Read source at a pinned commit and construct source links using https://github.com/{owner}/{repo}/blob/{commit}/{path}#L{line}. Authentication uses the dedicated service-account token in §11.7; reader access follows FR-086.

### 11.2 LLM provider

**Contract:** chat-completion with tool/function calling; system prompts; per-call token accounting; ideally prompt caching. Multiple model tiers (a strong model for investigation, a cheaper model for bulk classification) are SHOULD, not MUST.

*Recommendation on tiering:* match model capability to task complexity rather than running one model everywhere. Roles whose output gates the pipeline's quality — Triager evidence reasoning (FR-053/FR-054), Validator reproduction (FR-062), Detector exploratory mode (FR-042), Cartographer authoring (§5.3) — benefit measurably from the strongest model you have access to. High-volume mechanical work — rule-sweep evaluation (FR-039), label/severity assignment, summarization — tolerates a cheaper tier with little quality loss. The seed does not name models; the heuristic is "the more open-ended the reasoning, the more the stronger model earns its cost".

**Provider decision**: Use the Ollama API for LLM inference. The integration MUST satisfy the tool-calling, system-prompt, and token-accounting contract above. **Model decision**: Use the Ollama model tag `qwen3-coder:30b` for all LLM-backed roles in the first build, without role-based model tiering. Verify tool-calling, system-prompt handling, token accounting, and prompt-caching availability against the selected model and API interface during integration. **Hosting decision**: Host the Ollama API on a separate GPU server reachable from the Kubernetes cluster. Evaluation workloads may connect only to its explicitly authorized endpoint under the network allowlist in §9.1. **API interface decision**: Integrate through the native Ollama API. The server endpoint and connection settings MUST be configurable. **Connection decision**: Connect to the separate Ollama GPU server over private-network HTTP without API authentication. Configure the base URL at deployment; its host IP and port MUST be explicitly included in the operator-maintained network allowlist. The endpoint MUST remain on the private network. The actual host and port are deployment configuration values rather than fixed specification constants.

### 11.3 Datastore

**Contract:** durable storage for the finding store, work queue, index, coverage state, and session logs, with: atomic single-record update; query by fingerprint and by state; the ability to express "claim exactly one unclaimed record" without a race.

**Datastore decision**: Use SQLite for durable findings, the work queue, code index, coverage state, and session logs. One substrate service owns the SQLite database and exposes an API for agent reads, updates, and atomic work claims. Only that service may directly open the database files; agents on other workloads MUST use its API. Store the database on persistent storage with filesystem locking and durability semantics suitable for SQLite. Shared-state updates and work claims MUST use database transactions so concurrent agents cannot claim the same work unit or observe partially committed state. Claim recovery MUST follow the heartbeat-based liveness requirements. Service restarts MUST preserve committed state; the deployment MUST prevent overlapping database-owner instances.

### 11.4 Vector search

**Scope decision**: Semantic code search, code embeddings, and vector storage are deferred and out of scope for the first build. Structural and full-text code queries remain available through the Indexer. The seed embedding requirement is removed.

### 11.5 Deployment topology

**Contract:** run N agent processes with the substrate reachable from each; restart on operator command; the sandbox boundary of §9.1.

**Deployment decision**: Run Foundry-v2 evaluation workloads on an existing shared Kubernetes cluster in a dedicated evaluation namespace. This replaces the earlier operator-controlled single-machine topology. Foundry-v2 remains single-tenant with at most one active evaluation at a time; multiple agents may work concurrently within it. Hosted multi-tenancy and concurrent evaluations remain out of scope for the first build. Namespace placement MUST be combined with the enforced network and filesystem controls of §9.1; a namespace alone does not satisfy those controls.

### 11.6 Container / isolation runtime

**Contract:** run agent processes inside the §9.1 sandbox with the read-only mounts of FR-119.

**Isolation runtime decision**: Run evaluation agents and test execution in Kubernetes workloads. Mount target source read-only and provide writable mounts only for explicitly authorized working data and artifacts, consistent with FR-119. Enforce the network allowlist with Kubernetes NetworkPolicies as specified in §9.1.

### 11.7 Authentication model

**Contract:** the system can act on the issue tracker and read the target source under an identity the operator controls and can revoke.

**GitHub authentication decision**: Authenticate to GitHub using a dedicated service-account token controlled and revocable by the operator. Supply the token through a Kubernetes Secret, never through committed configuration or logs. Grant access only to the authorized source and reporting repositories and the operations required by §11.1. Use the service-account identity for tracker operations; record the originating agent role and evaluation in the internal audit trail.

### 11.8 Agent harness

**Contract:** run an LLM tool-use loop with a configurable system prompt, deliver steer/interrupt messages mid-session, capture a structured session log, report token usage.

**Agent harness decision**: Use a graph-based framework to coordinate LLM-backed role workflows. The framework integration MUST satisfy the configurable prompts, tool-use loop, mid-session steering and interruption, structured session logging, and token-accounting contract above, using the selected native Ollama API. **Framework decision**: Use LangGraph for Python. Integrate the selected native Ollama API for model calls. Persist workflow checkpoints through the substrate service so role progress survives restarts; agent workloads MUST NOT directly open the shared SQLite database. Operator steering and interruption MUST satisfy the harness contract, including at safe workflow boundaries. Heartbeat liveness, atomic work claims, evidence gates, and sandbox enforcement remain explicit Foundry-v2 responsibilities. Pin dependency versions during implementation planning.

### 11.9 Severity & classification schemes

Use CWE classification and CVSS 4.0 score/vector per FR-078 and FR-079.

### 11.11 Downstream export

See the publication destination decision at the end of §5.8 (following FR-086).

### 11.12 Testbed

**Availability decision**: A running deployment of the target is optional; source-only evaluations remain supported. Live probing and reproduction apply only when an authorized testbed is configured. **Testbed management decision**: The operator provisions and resets each optional testbed. Foundry-v2 MUST NOT automatically provision or reset it in the first build. Provide agents a structured inventory containing authorized endpoints and protocols, access requirements, in-scope and out-of-scope resources and actions, and any reset prerequisites or operator contact instructions. Store credential values separately from the inventory and resolve them through configured secret references. Agents MUST honor the inventory and operator scope; inventory changes require matching network-allowlist updates before newly authorized destinations are used.

---

## 12. Configuration Model

A single evaluation is defined by a single YAML configuration document with the following logical sections.

| Section | Contents | Consumed by |
|---|---|---|
| `target` | Where the source is; revision pin; include/exclude path scope. | Indexer, Cartographer, Detector, Triager |
| `testbed` | Structured inventory of authorized endpoints, protocols, access-secret references, scope and operator-managed reset procedure. Or an explicit "none". | Cartographer, Detector (exploratory), Triager, Validator |
| `goals` | Operator's attack goals (outcomes that matter) and scope backlog (components to test). Free text. | Cartographer, Coverage-Guide, Detector (exploratory) |
| `rules` | Hard rules (FR-121); out-of-scope hosts and actions. | All agents (system prompt); sandbox |
| `detection` | Reference to the detection rule corpus (FR-043); per-evaluation rule overrides. | Detector |
| `fleet` | Per-role: instance count, soft/hard session limits, role-specific prompt additions. | Orchestrator |
| `sandbox` | Operator-maintained IP/CIDR allowlist with ports/protocols; read-only paths; explicitly writable mounts; dedicated namespace. | Orchestrator, isolation runtime |
| `budget` | Spend cap; time cap; yield threshold, window, minimum runtime; severity point weights. | Orchestrator, budget governor |
| `integrations` | Concrete bindings for each §11 surface: credentials references (not values), endpoints, model ids. | All |

- **FR-145**: The configuration MUST be a single document (or a single directory treated as one) under version control alongside the evaluation's outputs.
- **FR-146**: Secrets (API keys, tokens, testbed credentials) MUST NOT be stored in the configuration document. The configuration references them; a separate non-version-controlled mechanism supplies them.
- **FR-147**: The Orchestrator MUST hot-reload `budget` and `rules` changes at runtime, in addition to the `fleet` hot-reload required by FR-010.
- **FR-148**: Changes to `target`, `sandbox`, and `integrations` MAY require a restart.
- **FR-149**: A configuration with unfilled required fields MUST fail FR-001 validation with a message naming each missing field.

**Configuration format decision**: Use YAML for evaluation configuration documents, including the structured testbed inventory. Validate configuration against the defined schema before evaluation startup. Configuration MUST contain secret references rather than real credentials or tokens.

---

## 13. Non-Functional Requirements

- **NFR-001 (Resumability)**: Every long-running operation (indexing, cartography, detection sweep, triage backlog) MUST be resumable after process death from its last persisted checkpoint, without re-doing completed work and without operator intervention.
- **NFR-002 (Idempotency)**: Re-running any stage on unchanged input MUST produce no new findings, issues, or side effects beyond updating timestamps.
- **NFR-003 (Determinism of structure)**: While LLM outputs are non-deterministic, the system's structural behavior (what gates on what, what writes where, what triggers what) MUST be deterministic and testable without a live model.
- **NFR-004 (Graceful degradation)**: Transient unavailability of any §11 integration MUST NOT crash the fleet; affected operations retry with backoff, the dashboard surfaces the degradation, and unaffected work continues.
- **NFR-005 (Cost proportionality)**: Spend SHOULD scale with target size and finding count, not with fleet size or wall-clock time. Adding agents increases throughput, not total cost to completion.
- **NFR-006 (Auditability)**: For any published finding, it MUST be possible to reconstruct from logs: which Detector technique surfaced it, the Triager's full investigation transcript, the Validator's reproduction attempt, and the Reporter's rendering decisions.
- **NFR-007 (No silent data loss)**: Any operation that discards, overwrites, or fails to persist work MUST log that it did so at a level the operator will see.
- **NFR-008 (Operator override)**: Every automated decision (verdict, exploited, coverage-complete, auto-stop) MUST be overridable by the operator, with the override recorded.
- **NFR-009 (Prompt-injection posture)**: The system MUST assume any content originating from the target (source code, documentation, testbed responses) may contain adversarial instructions, and MUST NOT grant such content the authority of operator instructions. Sandbox (FR-118) and read-only mounts (FR-119) are the enforcement layer; prompt hygiene is defense-in-depth only.

---

## 14. Out of Scope

The seed explicitly does not address:

- **Unauthorized testing.** Foundry-v2 assumes the operator is authorized to evaluate the target and to probe the testbed. Nothing here is designed for, or should be adapted to, testing systems without authorization.
- **Black-box-only evaluation.** The core pipeline assumes source access. A no-source mode is possible (Detector exploratory + Validator only) but is not what this seed describes.
- **Binary-only / vendored components.** Closed-source third-party binaries embedded in an otherwise source-available target are visible to dependency scanning (FR-040) but are out of scope for rule-based analysis (FR-039), triage evidence (FR-089), and Cartographer mapping.
- **Runtime protection.** Foundry-v2 finds vulnerabilities; it does not detect or block attacks at runtime.
- **Operational-environment assessment.** Foundry-v2 evaluates *software*. It does not assess the security posture of a running production environment: network configuration, exposed services, cloud or identity configuration, segmentation, or runtime detection coverage are not its inputs and not its outputs.
- **Red-teaming and adversary emulation.** Foundry-v2 does not plan or execute campaigns against live infrastructure, users, or identities. There is no role, FR, or guardrail for that mode of operation.
- **OSINT, social engineering, and human-targeted activity.** Open-source intelligence gathering, phishing, pretexting, and any other activity directed at people rather than software are out of scope. Every agent in the seed acts on code, dependencies, and an authorized testbed; none acts on humans.
- **Known-vulnerability (CVE) scanning.** Foundry-v2's Detector evaluates code against detection rules (FR-039) and dependencies against a vulnerability database for transitive risk (FR-040); it is not a CVE-matching scanner whose output is "this version of this component has CVE-X." Reports for findings that correspond to a known upstream CVE follow the operator's disclosure policy and are not the seed's primary output.
- **Compliance attestation.** Compliance mapping and compliance certification are out of scope for the first build.
- **Model training or fine-tuning.** Foundry-v2 consumes a frontier model as a service.
- **The content of detection rules, investigation prompts, severity rubrics, or report templates.** The seed specifies that these exist and where they plug in; authoring them is the receiving organization's work.

---

## 15. Resolved Decision Index

All seed decision points are resolved below. Earlier answers in the Clarifications log are historical; later decisions supersede them where explicitly recorded. Deployment-specific addresses, secrets, and pinned revisions are supplied through configuration.

| § | Question |
|---|---|
| 0 | System name: Foundry-v2 (resolved) |
| 1.5 | Authorized, source-available evaluations required (resolved) |
| 4.2 | Keep all eight core roles distinct (resolved) |
| 5.1 | Persistent Kubernetes service (resolved) |
| 5.2 | Indexer: Python and Go (resolved) |
| 5.2 / 11.4 | Embeddings and vector search deferred (resolved) |
| 5.3 | Cartographer does not gate startup; no Triager-only delay (resolved) |
| 5.3 | Cartographer: focused passes, one per document type (resolved) |
| 5.4 | All four detection techniques; live probing conditional on authorized testbed (resolved) |
| 5.4 | CodeGuard-based organization-wide corpus with custom rules in versioned Git (resolved) |
| 5.5 | Open-ended tool-use loop guided by fixed checklist (resolved) |
| 5.5 (ref. §7.2) | Keep needs-review internal; only true-positive creates GitHub issues (resolved) |
| 5.6 / 11.12 | Optional testbeds; operator provisioning/reset and structured inventory (resolved) |
| 5.6 | Authorized testing only notice plus setup prerequisites (resolved) |
| 5.8 / 11.9 | CWE with evidence-supported mapping rationale (resolved) |
| 5.8 / 11.9 | CVSS 4.0 score and vector (resolved) |
| 5.8 | GitHub commit-pinned permalinks; operator grants reader access before sharing (resolved) |
| 5.8 / 11.11 | No additional tracker export; GitHub Issues only (resolved) |
| 6.1 | Deep-Tester: deferred for first build (resolved) |
| 6.2 | Variant-Hunter: deferred for first build (resolved) |
| 6.3 | Attack-Mapper: deferred for first build (resolved) |
| 6.4 | Remediator: deferred for first build (resolved) |
| 6.5 | Self-Improver: deferred for first build (resolved) |
| 7.6 | Fixed GitHub label names and colors defined in §7.6 (resolved) |
| 9.1 / 11.6 | Kubernetes, read-only source mounts, Cilium-enforced NetworkPolicies, and operator-maintained IP/CIDR allowlists (resolved) |
| 10 | Web UI served by the Orchestrator (resolved) |
| 11.1 | GitHub repositories and GitHub Issues (resolved) |
| 11.2 | Native Ollama API; qwen3-coder:30b; private-network HTTP without API authentication on a separate GPU server; base URL supplied at deployment (resolved) |
| 11.3 | SQLite owned by one substrate service; agents access its API (resolved) |
| 11.5 | Existing shared Kubernetes cluster; dedicated namespace; one evaluation at a time (resolved) |
| 11.7 | Dedicated GitHub service-account token supplied via Kubernetes Secret (resolved) |
| 11.8 | LangGraph for Python (resolved) |
| 11.10 (removed) | Compliance mapping out of scope for first build (resolved) |
| 12 | YAML (resolved) |
| 13 / removed multi-tenant requirement | Multi-tenancy excluded; multi-tenant requirement removed (resolved) |

---

*End of Foundry-v2 DRAFT. See `.specify/memory/constitution.md` for governing principles and the accompanying quality and acceptance artifacts before planning.*
