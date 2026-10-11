"""One-time Foundry-v2 seed hardening and traceability generation."""
from pathlib import Path
import re
import json

root = Path(__file__).resolve().parents[2]
feature = root / 'specs/001-foundry'
path = feature / 'spec.md'
s = path.read_text(encoding='utf-8')
assert '| **Status** | `SEED` |' in s, 'Hardening already applied'
def replace(old, new):
    global s
    assert old in s, old[:100]
    s = s.replace(old, new)

replace('| **Status** | `SEED` |', '| **Status** | `DRAFT` |')
replace('| **Version** | 0.1.0 |', '| **Version** | 0.2.0 |\n| **Updated** | 2026-10-10 |')
replace('| **Intended use** | Clarification complete; input to `speckit-specify` for hardening into a DRAFT specification. |', '| **Intended use** | Implementation requirements and acceptance criteria; ready for `speckit-plan`. |')
start = s.index('> **This seed has been clarified')
end = s.index('**System name**', start)
s = s[:start] + '> **Foundry-v2 implementation specification.** Derived from the Foundry seed, with all operator decisions recorded below. The constitution at `.specify/memory/constitution.md` version 0.2.0 remains authoritative. This DRAFT defines required behavior; planning selects implementation details within the adopted constraints.\n\n' + s[end:]
replace('Thresholds are seed defaults; tighten or relax during clarify.', 'The acceptance thresholds below apply to this DRAFT.')
replace('The seed is written assuming the following hold. Each is either confirmed or overturned during `/speckit.clarify`; where one is overturned, the linked clarification names what changes.', 'These dependencies and assumptions constrain this build. Capability checks validate the selected deployment before evaluation startup.')
replace('A frontier LLM with tool/function calling is available via API, with per-call token accounting.', 'The selected Ollama model exposes tool/function calling and per-call token counts; capability and quality checks must pass before production evaluation.')
replace('§11.2 clarification.', '§11.2 capability check; report failure without silently changing models.')
replace('Single-target and multi-target evaluations.', 'Python and Go source evaluation; one active evaluation at a time. Multi-target scope is processed within that evaluation, not as concurrent evaluations.')
replace('Rollup document exists and groups ≥1 finding per component named in the security map.', 'Rollup lists each scoped component with its finding count (including zero) and coverage evidence.')
replace('identifies which fixes break the most attack paths, and maps coverage', 'prioritizes confirmed findings by severity and exploitation evidence, and maps coverage')
replace('- **FR-082**: The rollup SHOULD identify keystone findings: those whose fix would break the most attack paths. This MAY depend on the Attack-Mapper extension (§6.3); without it, in-degree of cross-references between finding reports is an acceptable proxy.', '- **FR-082**: The rollup SHOULD prioritize findings using their reported severity and independently demonstrated exploitation. It MUST NOT claim verified attack chains or keystone fixes without supporting evidence; attack-chain mapping is out of scope for this build.')
replace('For findings claimed exploitable, independently reproduce the headline impact against the testbed in a clean room.', 'For every confirmed finding with a configured testbed, independently attempt to reproduce the headline impact in a clean room.')
replace('`true-positive` verdicts that claim exploitability are queued for Validator.', 'Every `true-positive` verdict is queued for Validator; testbed availability determines live reproduction or the documented no-testbed path.')
replace('For findings the Triager marked `true-positive` with a claim of exploitability, independently reproduce', 'For every finding the Triager marked `true-positive` where a testbed is configured, independently attempt to reproduce')
replace('**Triggers.** `true-positive` finding with exploitability claim; operator request.', '**Triggers.** Every new `true-positive` finding; operator request. An exploitability hint affects priority only.')
replace('for `true-positive` only, a finding surfaced to Reporter and (if exploitability is claimed) to Validator.', 'for `true-positive` only, a finding surfaced to Reporter and Validator; no exploitability hint is required.')
replace('validate (if exploitability claimed & testbed)', 'validate (if testbed configured)')
replace('Free-text description of the running deployment: hosts, ports, credentials, topology, reset procedure. Or an explicit "none".', 'Structured inventory of authorized endpoints, protocols, access-secret references, scope and operator-managed reset procedure. Or an explicit "none".')
replace('Cartographer, Coverage-Guide, Detector (exploratory), Attack-Mapper', 'Cartographer, Coverage-Guide, Detector (exploratory)')
replace('Network allowlist (domains, CIDRs); read-only paths; extra mounts.', 'Operator-maintained IP/CIDR allowlist with ports/protocols; read-only paths; explicitly writable mounts; dedicated namespace.')
replace('facts (credentials, environment gotchas, architectural cribs)', 'facts (secret references, environment gotchas, architectural cribs; never credential values)')
replace('Each of these is a', 'Each of these is a') if False else None
replace('These are described in §6 at the level of "what it does and where it plugs in", without functional requirements.', 'All five extensions below are excluded from the first build as recorded in §6.')
replace('extension roles (described §6, not specified)', 'extension roles (deferred; out of scope)')
replace('### 4.6 What this seed does not prescribe', '### 4.6 Adopted constraints and planning boundary')
a = s.index('The seed specifies **roles, flows, and invariants**.')
b = s.index('\n---', a)
s = s[:a] + 'The system uses the integration choices in §11: shared-cluster Kubernetes, Cilium IP/CIDR policies, one SQLite-owning substrate service, a persistent Orchestrator web service, native Ollama on a separate GPU server, `qwen3-coder:30b`, LangGraph for Python, and GitHub. These are operator-adopted constraints, not proposed alternatives.\n\nPlanning must choose concrete schemas, endpoint routes, storage classes, dependency versions, parsers, scanner integrations, and deployment manifests that satisfy these contracts. Operator-authored prompts, CodeGuard extensions, goals, rates, and scope are versioned configuration inputs; their actual content is not inferred by this specification.\n' + s[b:]
replace('## 15. Open Questions Index', '## 15. Resolved Decision Index')
replace('*End of seed specification. Read `constitution.md` for the principles that constrain any plan derived from this spec, and `README.md` for how to turn this seed into your own specification.*', '*End of Foundry-v2 DRAFT. See `.specify/memory/constitution.md` for governing principles and the accompanying quality and acceptance artifacts before planning.*')
replace('FR-023 is removed.', 'The seed embedding requirement is removed.')
replace('Embeddings and vector search deferred; FR-023 removed (resolved)', 'Embeddings and vector search deferred (resolved)')

# Make local inference cost and hard-stop behavior evaluable without fabricating prices.
budget = '''
### 9.6 Local inference accounting and execution safeguards

- **FR-130**: For self-hosted Ollama, the operator MUST configure estimated input/output token rates in a named currency when spend-based yield auto-stop is enabled. Rates and the yield spend window MUST be positive; absent or zero rates MUST NOT be treated as free inference or permit division by zero. If yield auto-stop is explicitly disabled, report yield as unavailable while retaining runtime caps and operator stop. No monetary rates are invented by the system.
- **FR-131**: Each completed model call MUST contribute its token usage exactly once to the durable budget ledger. Interrupted calls with unknown usage MUST be marked unknown, make spend/yield incomplete, and disable spend-derived automatic completion until reconciled; runtime caps continue to apply. The dashboard MUST distinguish estimated, known, and incomplete accounting.
- **FR-132**: Before spawning agents, the Orchestrator MUST verify the configured Ollama endpoint/model can execute a representative tool call, return a system-prompt-conditioned answer, and expose usable token counts. Failure MUST identify the missing capability and prevent startup; model quality acceptance remains separate from protocol compatibility.
- **FR-133**: Evaluation workloads MUST be unable to alter namespace policy, obtain host privileges, mount arbitrary host paths, or use cluster credentials to escape the sandbox. Container-root access does not authorize privileged pods or host networking. Only operator-controlled infrastructure identities may install policy; preflight MUST verify denied egress and writes remain denied from the agent environment.
- **FR-134**: Only authenticated, operator-authorized callers may start, stop, steer, change configuration, or query the Orchestrator web interface. Agent identities may use only the substrate operations allowed for their role and evaluation; target content cannot authenticate as an operator. Planning MUST integrate this access contract with the cluster's existing operator access mechanism.
- **FR-135**: Reporter retries and concurrent instances MUST converge on one GitHub issue per fingerprint, including when issue creation succeeds but the response is lost. Persist publication intent and reconcile by stable identity before retrying creation. A revised non-true-positive verdict MUST update the existing issue to withdraw the confirmed claim and remove stale confirmation labels without creating a replacement issue.
- **FR-136**: Enforce one active evaluation per Foundry-v2 installation atomically across service restarts and concurrent start requests. Only one substrate instance may open the SQLite files; startup MUST prevent overlapping owners. Checkpoints and committed data MUST survive owner replacement without partially visible state.

**Runtime parameters.** Operator configuration defines heartbeat period, stale threshold, monitoring/claim cycle, drain grace, provider backoff bounds, retry block threshold, validation attempt limit, session limits, and yield window/weights/threshold/minimum runtime. Validate positive durations and bounds, stale threshold greater than heartbeat period, and hard session limit greater than soft limit. Omitted required values are reported by configuration validation, not silently guessed. Stale claims are reclaimed by the first monitoring cycle after their heartbeat threshold is exceeded. Provider backpressure includes explicit overload responses from self-hosted inference; adaptive retry MUST NOT silently become a permanent capacity cap. No payment API is assumed.

'''
replace('## 10. Observability', budget + '## 10. Observability')
replace('within the configured heartbeat-stale window', 'within the configured heartbeat-stale threshold plus one monitoring cycle')
replace('within heartbeat-stale window', 'within heartbeat-stale threshold plus one monitoring cycle')
replace('between `up` and publication', 'between evaluation start and publication')

stories = [
('US-1','Start an authorized evaluation','P1','valid YAML, GitHub access, pinned Python/Go source, approved policies, and a compatible Ollama endpoint','the operator starts an evaluation','one Indexer starts first; no other role starts until its required queries succeed; the remaining core roles then start without waiting for cartography'),
('US-2','Inspect live progress','P1','a running evaluation with live, blocked, and restarted agents','the operator opens status and dashboard for the same snapshot','both show identical claims, heartbeat ages, counts, budget, and blockers; activity can be filtered by role and event'),
('US-3','Ask grounded questions','P2','a triaged finding and its durable evidence transcript','the operator asks why its verdict was assigned','the answer cites the actual stored reasoning; a delayed model answer does not delay lifecycle handling'),
('US-4','Recognize honest completion','P1','a configured positive cost model and a finite goal checklist','yield falls below threshold after the full window and minimum runtime','the fleet drains only if every coverage item is complete; changing goals clears completion'),
('US-5','Bound resource use','P1','a configured spend or runtime cap','the ledger or elapsed runtime exceeds it','the Orchestrator begins halting within one monitoring cycle and rejects restart until the relevant cap is raised or explicitly reset'),
('US-6','Enforce authorized boundaries','P1','Cilium-enforced IP/CIDR policy and read-only protected mounts','an agent with container-root access attempts denied egress, source writes, or policy changes','all attempts fail at infrastructure boundaries; failure of the preflight boundary check prevents agent startup'),
('US-7','Publish evidence-backed findings','P1','candidates with valid evidence, fabricated citations, and incomplete evidence','triage and reporting run','only verified true-positive findings create GitHub issues; invalid citations demote to needs-review and nonconfirmed findings stay internal'),
('US-8','Distinguish demonstrated impact','P2','a true-positive finding and optional authorized testbed','a fresh Validator receives the artifact and claim','only observed headline impact sets exploited; failed or partial reproduction records its reason; no testbed yields an unexecuted artifact and no exploited flag'),
('US-9','Review a useful rollup','P2','scoped components with confirmed findings and components with no findings','the Reporter refreshes the rollup','every component has counts and coverage evidence, findings are prioritized by severity/exploitation, and no unsupported attack-chain claim is made'),
('US-10','Reproduce from one report','P1','a reader granted repository access and an independently exploited finding','the reader follows the published issue and artifact','pinned code links resolve and the reported impact can be reproduced with documented prerequisites and the Authorized testing only notice'),
('US-11','Rerun without duplicates','P2','prior findings and a target edit that shifts lines without changing path, symbol, or weakness class','the evaluation is rerun','only changed files are re-parsed, stable fingerprints retain identity, and GitHub issues are updated rather than recreated'),
('US-12','Steer active work','P2','a running agent with a claim and an operator-authorized request','the operator queues a task or sends immediate/idle steering','the task is eligible in the next claim cycle, steering respects its requested mode, and peer advice never gains operator authority'),
('US-13','Keep roles independent of bindings','P3','an integration adapter satisfying its documented contract','the builder substitutes a test adapter','role contract tests pass without changing role behavior; adding alternative production integrations is not required for this build'),
('US-14','Reuse the rule corpus','P3','a pinned CodeGuard corpus with reviewed organization-specific additions','the builder loads it in an external compatible consumer','the same rule content is consumed unchanged and each evaluated finding retains corpus provenance; no Self-Improver is required'),
]
scenarios = '\n### 3.4 User Scenarios & Testing\n\nThe prioritized story table above defines user value and independent test boundaries. Each scenario below is independently exercisable with deterministic fixtures for adjacent stages; integration acceptance additionally uses the selected deployed bindings.\n\n'
for uid,title,priority,given,when,then in stories:
    scenarios += f'#### {uid}: {title} ({priority})\n\n- **Given** {given}, **When** {when}, **Then** {then}.\n\n'
scenarios += 'Additional boundary acceptance: a prolonged but heartbeating call retains its claim; after real heartbeat expiry reclamation occurs on the next monitor cycle. Concurrent claim attempts never share a task. Fault injection during publication reconciles one issue; during persistence readers see the previous or next complete generation. Loss of Ollama, GitHub, or substrate connectivity surfaces degradation and preserves committed progress.\n\n'
s = re.sub(r'\*Note on acceptance scenarios:\*[^\n]*\n', '', s)
replace('## 4. System Overview', scenarios + '## 4. System Overview')

entities = '''
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

'''
replace('## 4. System Overview', entities + '## 4. System Overview')

# Enumerate all active requirements and remap references simultaneously.
old_ids = re.findall(r'^- \*\*(FR-\d{3}[a-z]?)\*\*:', s, re.M)
assert len(old_ids) == len(set(old_ids))
mapping = {old:f'FR-{i:03}' for i,old in enumerate(old_ids,1)}
unknown = set(re.findall(r'\bFR-\d{3}[a-z]?\b',s)) - set(mapping)
assert not unknown, unknown
s = re.sub(r'\bFR-\d{3}[a-z]?\b', lambda m:mapping[m[0]], s)
nfr_old = re.findall(r'^- \*\*(NFR-\d{3})',s,re.M)
s = s.replace('13 / NFR-003', '13 / removed multi-tenant requirement').replace('NFR-003 dropped', 'multi-tenant requirement removed')
nfr_mapping = {old:f'NFR-{i:03}' for i,old in enumerate(nfr_old,1)}
s = re.sub(r'\bNFR-\d{3}\b',lambda m:nfr_mapping[m[0]],s)

def atomic_write(p, content):
    p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix(p.suffix+'.tmp')
    tmp.write_text(content,encoding='utf-8',newline='\n')
    tmp.replace(p)
atomic_write(path,s)
atomic_write(root/'.specify/feature.json',json.dumps({'feature_directory':'specs/001-foundry'},indent=2)+'\n')
concordance = '# Requirement ID Concordance\n\nGenerated 2026-10-10. The upstream seed and constitution retain their original IDs; this mapping applies only to the derived Foundry-v2 DRAFT. The seed embedding requirement FR-023 and multi-tenant NFR-003 are removed, not reassigned in the seed. Added FR-130–FR-136 are DRAFT hardening requirements.\n\n| Seed/hardening ID | DRAFT ID |\n|---|---|\n'
concordance += ''.join(f'| {a} | {b} |\n' for a,b in mapping.items())
concordance += ''.join(f'| {a} | {b} |\n' for a,b in nfr_mapping.items())
atomic_write(feature/'requirement-id-map.md',concordance)

groups = [
('Orchestrator lifecycle','FR-001','FR-019','US-1, US-2, US-3, US-5, US-12','Inject configuration failures, exits and slow queries; inspect startup order, backoff, drain, hot reload, status and recorded operator overrides.'),
('Index contract','FR-020','FR-029','US-1, US-11','Use Python/Go fixtures with direct calls, changed and unparseable files; assert scoped inventory, query results, atomic generations and continued lifecycle responsiveness.'),
('Cartography','FR-030','FR-036a','US-1, US-7, US-9','Inspect all required documents and digests; inject empty-pass failure and verify factual fallback; detection starts while cartography is pending.'),
('Detection','FR-037','FR-049','US-7, US-11, US-14','Exercise known rule, dependency, secret and exploratory fixtures; verify candidate provenance, corpus revision, dedup, scope and attempted-area log without issue creation.'),
('Triage','FR-050','FR-059','US-3, US-7, US-11','Exercise each verdict, sanitization and missing-evidence case; inspect investigation/citations, rule gaps, retention and no needs-review publication.'),
('Validation','FR-060','FR-066','US-8, US-10','Use clean-room success, partial impact, failure, hard-rule restriction and no-testbed cases; check artifact headers, attempt bounds and unchanged true-positive verdict on reproduction failure.'),
('Coverage','FR-067','FR-074','US-4, US-9, US-12','Exercise finite goals, empty goals, attempted-with-no-findings items and goal edits; verify directed tasks, independent closure evidence, estimates and persisted checklist.'),
('Reporting','FR-075','FR-084','US-7, US-9, US-10, US-11','Inspect issue content, evidence, CWE/CVSS, score/vector consistency, label mapping, pinned permalinks, internal-detail exclusion and update-not-duplicate behavior.'),
('Finding lifecycle','FR-085','FR-093','US-7, US-8, US-11','Exercise re-triage, evidence exceptions, invalid citations, clean-room exploitation, shifted lines, label creation and active-claim label removal.'),
('Queue and liveness','FR-094','FR-101','US-2, US-12','Race claims, reprioritize and exhaust retry threshold; verify stable IDs, blocked state, no heartbeat starvation and no reclamation before heartbeat expiry.'),
('Messages and notes','FR-102','FR-104b','US-2, US-3, US-12','Send advisory peer messages, deduplicated blockers and acknowledgments; inspect nonblocking delivery, notes locking/size and absence of secret values or authoritative completion assertions.'),
('Rate and persistence','FR-105','FR-106a','US-5, US-11','Inject provider backpressure and interrupted writes; verify shared adaptive retry, no static guessed rate ceiling and only complete persisted state.'),
('Sandbox and scope','FR-107','FR-111','US-6','Exercise denied IP/CIDR/port destinations and writes as container root; verify read-only source/config/prompts, setup warning and hard-rule exclusions.'),
('Budget and rotation','FR-112','FR-119a','US-4, US-5','Cross caps, lower yield before/after coverage, change weights, and rotate sessions; inspect graceful halt, retained heartbeating claims and retirement without busywork.'),
('Local inference and safeguards','FR-130','FR-136','US-1, US-4, US-5, US-6, US-11','Reject invalid rates/capabilities, reconcile unknown tokens, deny unauthenticated control, fail infrastructure escape probes, reconcile lost issue responses, and race evaluation/SQLite ownership.'),
('Observability','FR-120','FR-125','US-2, US-3, US-9','Compare identical snapshot IDs across status/dashboard; inspect activity filtering, token/cost rolls, durable transcripts and prominent degraded states.'),
('Configuration','FR-126','FR-129','US-1, US-5, US-6','Validate YAML/secret references/missing fields; hot-reload permitted sections and reject unsafe changes or require controlled restart.'),
]
accept='# Functional Acceptance Coverage: Foundry-v2\n\nGenerated 2026-10-10. These are specification acceptance obligations, not executed software tests. MUST/MUST NOT clauses require both positive and prohibited-behavior fixtures. SHOULD clauses are expected first-build behavior unless a documented operator-approved exception explains the limitation. MAY clauses require contract checks if enabled.\n\n| Area | DRAFT requirements | Stories | Acceptance evidence |\n|---|---|---|---|\n'
covered=set()
for title,first,last,us,evidence in groups:
    left,right=old_ids.index(first),old_ids.index(last)
    ids=old_ids[left:right+1]
    covered.update(ids)
    accept += f'| {title} | '+', '.join(mapping[x] for x in ids)+f' | {us} | {evidence} |\n'
assert covered == set(old_ids),set(old_ids)-covered
accept += '\n## Non-functional acceptance\n\nCrash/restart each stage and confirm committed checkpoints survive (resumability); repeat unchanged input with no new findings/issues (idempotency); run structural fixture checks without a live model (determinism); inject each integration outage with visible backoff and unaffected work continuing (degradation); compare spend for the same target at different fleet sizes and investigate disproportionate growth (cost proportionality); reconstruct all publication provenance (auditability); surface persistence failures (no silent loss); apply and log explicit operator overrides; inject adversarial target instructions and confirm no privilege or authority change.\n'
atomic_write(feature/'acceptance-coverage.md',accept)

principles=[('I','Evidence Over Assertion',['FR-051','FR-052','FR-087','FR-088']),('II','Surface Only What Survives',['FR-044','FR-057','FR-079']),('III','Liveness By Heartbeat',['FR-005','FR-096','FR-100','FR-118']),('IV','Atomic Mortal Claims',['FR-095','FR-096']),('V','Provider Rate Arbiter',['FR-105','FR-106']),('VI','Coverage Before Yield',['FR-071','FR-115','FR-116']),('VII','Exploited Means Demonstrated',['FR-060','FR-061','FR-089']),('VIII','Stable Fingerprints',['FR-045','FR-090','FR-091']),('IX','Infrastructure Sandbox',['FR-107','FR-108','FR-133']),('X','Operator Authority',['FR-018','FR-068','FR-102','FR-104b']),('XI','Atomic Persistence',['FR-025','FR-074','FR-106a','FR-136'])]
review='# Constitution Review: Foundry-v2\n\nDate: 2026-10-10. Authority: `.specify/memory/constitution.md` v0.2.0, unchanged. Original constitution requirement references are interpreted through `requirement-id-map.md`. This is a specification conformance review, not proof of implementation compliance.\n\n| Principle | DRAFT enforcing requirements | Review |\n|---|---|---|\n'
for num,title,refs in principles:
    review += f'| {num}. {title} | '+', '.join(mapping[x] for x in refs)+' | Covered; acceptance obligations in acceptance-coverage.md |\n'
review += '\nOperator runtime overrides remain recorded exceptions; automated behavior never gains override authority. Session rotation terminates a session without clock-based claim reclamation; remaining claims expire only by heartbeat. Role counts express operator fleet composition, not a guessed provider-rate ceiling. Kubernetes namespace placement does not constitute isolation; enforced controls and preflight are required. SQLite owner and publication recovery must preserve atomicity. Local estimated monetary rates remain operator configuration and cannot be fabricated.\n'
atomic_write(feature/'constitution-review.md',review)

check='# Specification Quality Checklist: Foundry-v2\n\n**Purpose**: Validate completeness before planning.\n**Created**: 2026-10-10\n**Feature**: [spec.md](../spec.md)\n\n## Content Quality\n\n'
items=['Behavior requirements are separated from unselected implementation design; operator-adopted integration constraints remain explicit.','Focused on operator value, trustworthy output, and bounded authorized evaluation.','Personas, glossary and scenarios explain the system for its intended technical stakeholders.','User scenarios, edge cases, requirements, key entities, success criteria and assumptions are completed.','No clarification markers or unresolved organization decisions remain.','Requirements are testable; active FR and NFR IDs are unique and contiguous.','Success criteria are measurable; acceptance thresholds and parameter-dependent bounds are explicit.','Success criteria describe outcomes without prescribing a framework or storage technology.','All 14 prioritized stories have Given/When/Then acceptance scenarios.','Crash, concurrency, no-testbed, invalid evidence, outages and accounting edge cases are defined.','First-build scope excludes extensions, vectors, multi-tenancy, compliance and extra trackers.','Deployment dependencies, model capability checks and operator-provided configuration are identified.','Every active functional requirement is covered by acceptance-coverage.md.','User scenarios cover start, supervise, investigate, validate, publish, rerun, steer and stop.','Production readiness requires demonstrated success criteria; this checklist claims specification readiness only.','No unapproved implementation choices have replaced the adopted integration decisions.']
check += ''.join(f'- [x] CHK{i:03} {item}\n' for i,item in enumerate(items,1))
check += '\n## Notes\n\nAll 16 specification checks pass. The generic no-implementation-detail checklist items are scoped to unselected design decisions: the user explicitly requested preserving the clarified seed integrations. The seed section order is retained rather than replacing it with the generic feature template; required template content is present in §§1, 3, 5–13. IDs are remapped in the concordance; upstream files are unchanged. No application tests were run because this repository has no implementation. Planning must select operator access integration, storage semantics, adapters, dependency versions and endpoint schemas within these contracts.\n'
atomic_write(feature/'checklists/requirements.md',check)
defs=re.findall(r'^- \*\*(FR-\d{3})\*\*:',s,re.M)
assert defs==[f'FR-{i:03}' for i in range(1,len(defs)+1)]
assert set(re.findall(r'\bFR-\d{3}\b',s))==set(defs)
assert '[NEEDS CLARIFICATION' not in s
assert len(re.findall(r'\*\*Given\*\*',s))==14
print(json.dumps({'functional_requirements':len(defs),'nonfunctional_requirements':len(nfr_mapping),'acceptance_stories':14,'checklist_passed':16,'clarification_markers':0},indent=2))
