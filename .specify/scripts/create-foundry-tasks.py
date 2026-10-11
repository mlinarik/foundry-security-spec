"""Generate reviewable implementation backlog and requirement traceability."""
from pathlib import Path
import json
import re
from collections import Counter

ROOT = Path(__file__).resolve().parents[2]
FEATURE = ROOT / 'specs/001-foundry'
prior_completed = set()
if (FEATURE/'tasks.md').exists():
    for line in (FEATURE/'tasks.md').read_text(encoding='utf-8').splitlines():
        if re.match(r'^- \[[xX]\] T\d{3}', line):
            prior_completed.add(re.sub(r'^- \[[xX]\]', '- [ ]', line))
rows = []

def add(group, kind, text, refs='', parallel=False):
    rows.append(dict(id=f'T{len(rows)+1:03}', group=group, kind=kind,
                     text=text, refs=refs, parallel=parallel))

def batch(group, kind, lines, parallel=False):
    for line in lines.strip().splitlines():
        text, refs = line.split(' | ')
        add(group, kind, text, refs, parallel)

batch('Setup', 'implementation', '''
Create CPython 3.12 package, three process entrypoints, CLI/config modules and planned directory layout in pyproject.toml and src/foundry_v2/__init__.py; keep eight role identities distinct | NFR-003
Resolve plan.md pins on Linux Python 3.12 into requirements.lock with hashes, install and smoke-test FastAPI/LangGraph/Ollama/tree-sitter/CVSS; record any necessary compatibility correction in specs/001-foundry/dependency-resolution.json before using it | NFR-003
Build pinned Linux service/worker images and verify scanner archive checksums for OSV-Scanner 2.6.0 and Gitleaks 8.30.1 in deploy/images/Dockerfile and deploy/images/scanners.json; resolve immutable image digests | NFR-003
Create pytest markers and seeded Python/Go, clean, adversarial, scanner and provider/GitHub fixture inventory in tests/conftest.py and tests/fixtures/manifest.json; distinguish live_cluster/live_model tests | NFR-003
Configure deterministic unit/contract/integration CI and explicit opt-in live suites in .github/workflows/validate.yml; never embed credentials or claim skipped checks passed | NFR-003
''')
batch('Foundation', 'test', '''
Write single-owner/start-race, claim-race/late-generation, queue auto-block/stable-ID/reprioritization, CAS/idempotency, role/evaluation isolation and transaction crash tests in tests/integration/test_substrate_foundation.py using data-model.md and runtime.md | FR-097,FR-098,FR-099,FR-100,FR-103,FR-117,FR-136,FR-138,NFR-007
Write checkpoint pending-write/resume/namespace/unsafe-codec and blob fault tests in tests/contract/test_checkpoint_contract.py against a test-only reference saver | FR-117,NFR-001,NFR-002
''', True)
batch('Foundation', 'implementation', '''
Define shared strict DTOs, stable IDs and contract errors from contracts/openapi.json in src/foundry_v2/contracts/models.py; preserve all 41 operation IDs and role identities | NFR-003
Create all data-model.md tables, foreign keys, unique constraints, history, migration versioning and backup-before-migration in src/foundry_v2/substrate/migrations/001_initial.sql and src/foundry_v2/substrate/migrate.py | FR-087,FR-088,FR-117,FR-138
Implement lifetime owner lock, owner epochs, WAL/FULL/foreign keys, serialized short immediate transactions, uncertain-owner refusal and atomic active-evaluation reservation in src/foundry_v2/substrate/owner.py | FR-117,FR-138
Implement actor-scoped idempotency receipt plus mutation transactions, CAS conflicts, cursor lists and safe error responses in src/foundry_v2/substrate/transactions.py | FR-117,NFR-002,NFR-007
Implement immutable SHA-256 staging/fsync/rename, committed visibility, safe orphan handling and backup/restore manifest verification in src/foundry_v2/substrate/blobs.py and src/foundry_v2/substrate/backup.py | FR-117,NFR-001,NFR-007
Implement TokenReview operator allowlist and hashed expiring role/evaluation/session substrate tokens, revocation and separate infrastructure registration authority in src/foundry_v2/api/auth.py and src/foundry_v2/substrate/auth.py | FR-136,NFR-009
Implement substrate HTTP client and foundation endpoints for session registration, snapshot, blobs and generation reads in src/foundry_v2/substrate/app.py and src/foundry_v2/workers/client.py; fail closed during unknown ownership | FR-117,FR-136,FR-138,NFR-004
Implement owner checkpoint tuple/pending-write endpoints and controlled typed codec in src/foundry_v2/substrate/checkpoints.py; restrict fresh reproducer access to its own thread | FR-117,NFR-001
Implement asynchronous BaseCheckpointSaver methods and pinned-version serialization/versioning conformance in src/foundry_v2/checkpoints/http_saver.py; encode empty namespace as _root and preserve parent/pending writes | NFR-001,NFR-002
Implement append-only sequenced events, redacted transcript chunks, explicit persistence-failure events and complete generation pointer swaps in src/foundry_v2/substrate/audit.py | FR-117,FR-141,NFR-006,NFR-007
Implement stable-ID named queues, atomic task/finding/file claims, generation fences, CAS writes and configurable release-count auto-block in src/foundry_v2/substrate/claims.py and src/foundry_v2/substrate/tasks.py | FR-097,FR-098,FR-099,FR-100,FR-101,FR-103
Implement receipt-clock heartbeats, stale-only reaper and restart grace in src/foundry_v2/substrate/liveness.py; neither rotation nor slow calls reclaims healthy claims | FR-006,FR-099,FR-104
Implement independent heartbeat sender, graph checkpoint handoff, secret-free tool execution boundary and advisory/operator origins in src/foundry_v2/workers/runtime.py and src/foundry_v2/workers/heartbeat.py | FR-003,FR-104,FR-105,NFR-001,NFR-009
Define injection interfaces for provider/index/substrate/publisher/deployment/clock and a fixed eight-role graph registry in src/foundry_v2/integrations/ports.py and src/foundry_v2/roles/registry.py; use deterministic fakes until each story binding is ready | FR-013,NFR-003
''')
add('Foundation', 'verification', 'Run foundation fault/race/auth/checkpoint suites and capture failures and recovery assertions in tests/integration/test_substrate_foundation.py; foundation blocks every story until passed', 'FR-117,FR-136,FR-138,NFR-001,NFR-007')

stories = {
1: ('Start an authorized evaluation', 'P1', 'Fresh checkout and valid fixture config: CLI up starts Indexer first, required scoped queries pass, then remaining seven role types run without a cartography gate; invalid config/capability and concurrent starts fail safely.'),
2: ('Inspect live progress', 'P1', 'Using synthetic substrate state and delayed provider responses, status/dashboard at the same snapshot ID show every session/claim, counts, coverage, budget and blockers; event reconnect and outages remain visible.'),
4: ('Know when evaluation is done', 'P1', 'With fixture ledger/clock, finite explicit goals and recorded attempts, completion occurs only with all coverage, positive full window, minimum runtime and complete accounting; open/changed goals or unknown usage prevent completion.'),
5: ('Bound spend and runtime', 'P1', 'Inject token frames, unknown calls and cap crossings: exactly-once accounting and one-cycle halt hold; restart after exhaustion is refused until cap raise; runtime watchdog works during substrate/provider failure.'),
6: ('Enforce runtime boundaries', 'P1', 'On an explicitly authorized isolated deployment, container-root probe cannot reach disallowed IPv4/IPv6/node/metadata/API destinations or write protected mounts; worker escalation and model access to controller/publisher credentials are denied.'),
7: ('Surface evidence-supported findings', 'P1', 'Seeded rule/dependency/secret/exploratory fixtures exercise all verdicts and evidence gates; only verified TP produces publication intent; fabricated citations, unsupported impact and needs-review never publish; human sample precision is at least 90%.'),
10: ('Reproduce from one report', 'P1', 'With fixture validation result, report contains justified CWE, valid CVSS 4.0, pinned source links, fixed labels and self-contained reproduction; lost create response reconciles one issue; authorized live proof waits for US8.'),
3: ('Ask grounded questions', 'P2', 'A question about a known verdict cites its stored reasoning; a delayed answer leaves status/drain/heartbeat responsive, and target instructions cannot authorize overrides.'),
8: ('Distinguish demonstrated impact', 'P2', 'Fresh reproducer gets only claim/artifact/report; live headline impact alone sets exploited; partial/failed/prohibited/no-testbed outcomes preserve TP and record reasons; independent human reproduces every exploited sample.'),
9: ('Review a useful rollup', 'P2', 'Fixture components include zero-finding cases: one rollup groups counts and prioritizes severity/exploitation with original-goal attempt evidence; unsupported chain/keystone claims are absent.'),
11: ('Rerun without duplicates', 'P2', 'Unchanged and line-shifted fixture reruns add zero findings/issues, reuse unchanged parses and patch edges; prior TP triggers fresh investigation, changed verdict withdraws confirmation on the original issue.'),
12: ('Steer active work', 'P2', 'Operator priority task is acquired next claim cycle; idle/immediate steering follows mode with durable handoff, peer hints do not override intent, and explicit overrides preserve audit.'),
13: ('Keep roles independent of bindings', 'P3', 'Run the same role contracts with alternate fake provider/tracker/store/deployment adapters without role edits; production remains the selected stack.'),
14: ('Reuse the rule corpus', 'P3', 'Load pinned corpus plus reviewed organization additions unchanged into an external compatible consumer, preserving digest/provenance; rule gaps are reviewable without Self-Improver.')}

batch(1, 'test', '''
Write startup-order, invalid/missing config, cap guard, model capability, race and crash-loop acceptance tests in tests/acceptance/test_us1_start.py with fake adjacent roles | FR-001,FR-002,FR-003,FR-004,FR-005,FR-006,FR-007,FR-008,FR-010,FR-011,FR-013,FR-134,FR-138,FR-145,FR-146,FR-148,FR-149
Write scoped Python/Go inventory/static-call/query, parse-skip and atomic-generation fixtures in tests/unit/test_indexing.py including a CPU-bound parse while status responds | FR-021,FR-022,FR-023,FR-024,FR-025,FR-026,FR-028,FR-029,FR-030
''', True)
batch(1, 'implementation', '''
Implement YAML shape plus runtime semantic validation, all missing-field errors, versioned config and secret references in src/foundry_v2/config.py; reject placeholder revisions/unsafe endpoints and controlled-restart fields | FR-001,FR-145,FR-146,FR-148,FR-149
Implement native Ollama tool/system/terminal-token capability probes, model digest and aggregated GitHub/testbed/storage/policy preflight in src/foundry_v2/integrations/preflight.py; binding invokes US6 policy probes when installed | FR-011,FR-134
Implement scoped commit-pinned source acquisition and deterministic Python/Go parser inventories/static and resolvable indirect edges in src/foundry_v2/indexing/parser.py and src/foundry_v2/indexing/source.py; mark unresolved calls and visible skipped files | FR-021,FR-022,FR-023,FR-028,FR-029
Implement function/body/caller/callee/symbol/text queries, staged complete generation publication and readiness assertions in src/foundry_v2/indexing/service.py and src/foundry_v2/roles/indexer.py; isolate parsing in its worker process | FR-024,FR-025,FR-026,FR-030
Implement sole-authority persisted Job reconciliation/adoption, Indexer readiness gate, desired role counts, exponential unlimited-attempt crash retry and graceful drain in src/foundry_v2/orchestrator/lifecycle.py | FR-002,FR-003,FR-004,FR-005,FR-006,FR-007,FR-008,FR-013
Implement atomic config revisions and fleet count reconciliation in src/foundry_v2/orchestrator/configuration.py; safely restart changed target/sandbox/integrations and wire rules/budget handlers supplied by later stories | FR-010,FR-145,FR-147,FR-148
Implement authenticated start/control/config endpoints and CLI up/preflight/status/stop in src/foundry_v2/api/evaluations.py and src/foundry_v2/cli.py; provide one-command up alias and async preflight/index states | FR-001,FR-007,FR-138,FR-149
''')
add(1, 'verification', 'Run US1 fixture startup and parser tests in tests/acceptance/test_us1_start.py; record real-binding startup as pending until US5/US6/US7/US10 and deployment inputs are ready', 'FR-004,FR-025,FR-030,FR-134,FR-138')

batch(2, 'test', '''
Write snapshot equality, live feed reconnect/gap, outage, message dedup/ack and redaction acceptance tests in tests/acceptance/test_us2_visibility.py | FR-009,FR-107,FR-108,FR-109,FR-110,FR-139,FR-140,FR-141,FR-142,FR-143,FR-144,NFR-006,NFR-007
''')
batch(2, 'implementation', '''
Implement owner-consistent fleet/finding/coverage/ledger/queue/message snapshot and status in src/foundry_v2/substrate/snapshots.py and src/foundry_v2/api/status.py; no status LLM calls | FR-009,FR-139,FR-143
Implement nonblocking typed operator messages, fleet equivalence dedup, acknowledgment/removal and no finding/progress payload policy in src/foundry_v2/substrate/messages.py and src/foundry_v2/api/messages.py | FR-107,FR-108,FR-109,FR-110
Implement structured replayable turns/tools/results/usage and per-role token/cost/tool histograms in src/foundry_v2/workers/transcripts.py and src/foundry_v2/substrate/metrics.py | FR-141,FR-142,NFR-006,NFR-007
Implement filtered SSE with durable cursors/snapshot IDs and retention-gap refresh in src/foundry_v2/api/events.py | FR-140,FR-143
Implement escaped dashboard, memory-only bearer handling, same-origin requests, blocker prominence and degraded states in src/foundry_v2/templates/dashboard.html and src/foundry_v2/static/dashboard.js; render unknown/estimated spend explicitly | FR-139,FR-143,FR-144,NFR-009
''')
add(2, 'verification', 'Verify visibility and reconnect acceptance with injected provider/GitHub/substrate failures in tests/acceptance/test_us2_visibility.py; unaffected operations continue and failure messages contain no secrets', 'FR-143,FR-144,NFR-004,NFR-007')

batch(4, 'test', '''
Write finite/empty/edited-goal, no-findings attempt, complete-window/min-runtime/unknown-ledger and restart acceptance in tests/acceptance/test_us4_completion.py; use ledger/clock fixtures until US5 | FR-069,FR-070,FR-071,FR-072,FR-073,FR-074,FR-075,FR-076,FR-126,FR-127,FR-128,FR-132,FR-133
''')
batch(4, 'implementation', '''
Implement persisted finite component-goal checklist with credible-attempt bars, empty/template-goal waiting, factual partial-map context and cycle estimates in src/foundry_v2/roles/coverage_guide.py | FR-069,FR-070,FR-075,FR-076
Implement append-only attempt matching, evidence-based closure, directed actionable tasks and goals-revision invalidation in src/foundry_v2/substrate/coverage.py; Coverage-Guide cannot detect/triage/validate or close its own tasks | FR-071,FR-072,FR-073,FR-074,FR-076
Implement severity/exploitation-weighted trailing positive-spend window and atomic conjunction of coverage revision/window/runtime/known accounting in src/foundry_v2/governance/completion.py; disabled yield is unavailable | FR-126,FR-127,FR-128,FR-132,FR-133
Wire audited completion reason, drain signal and dashboard remaining-work/yield state in src/foundry_v2/orchestrator/completion.py; use US5 ledger port instead of duplicate accounting | FR-073,FR-075,FR-127
''')
add(4, 'verification', 'Run completion boundary fixtures and checkpoint restart in tests/acceptance/test_us4_completion.py; full live SC-006 is a final integration gate after US5 and detection/reporting', 'FR-070,FR-073,FR-076,FR-127')

batch(5, 'test', '''
Write terminal-token exactly-once/timeout-unknown, fleet 429/503, cap resume, local watchdog and healthy-claim rotation tests in tests/acceptance/test_us5_budget.py | FR-012,FR-115,FR-116,FR-123,FR-124,FR-125,FR-129,FR-130,FR-131,FR-132,FR-133,FR-147
''')
batch(5, 'implementation', '''
Implement native Ollama chat/tools/schema streaming and ledger call IDs in src/foundry_v2/integrations/ollama.py; shared adaptive Retry-After/429/503 backpressure comes from substrate without guessed inference ceilings | FR-115,FR-116,FR-124,FR-133
Implement durable model-call reservation/finalization/unknown reconciliation, operator rates/currency and estimated fraction in src/foundry_v2/substrate/budget.py; expose model-calls/backpressure endpoints | FR-123,FR-124,FR-132,FR-133
Implement cumulative cross-run spend/runtime caps, unset-cap warning, one-cycle halt, cap-exhaustion resume guard and monotonic controller watchdog during substrate loss in src/foundry_v2/governance/budget.py | FR-012,FR-123,FR-125
Implement soft wrap-up/hard termination/session renewal plus idle retirement without busywork in src/foundry_v2/orchestrator/rotation.py; surviving held claims expire only on stale heartbeat, not rotation clock | FR-129,FR-130,FR-131
Wire live budget/weight/rate config reload and US4 completion ledger in src/foundry_v2/orchestrator/budget_configuration.py; explicit operator auto-stop override retains audit | FR-128,FR-132,FR-147,NFR-008
''')
add(5, 'verification', 'Run combined real-ledger completion/cap/rotation/slow-call fixtures in tests/acceptance/test_us5_budget.py; prove heartbeats continue and incomplete accounting prevents spend-derived completion', 'FR-012,FR-115,FR-116,FR-123,FR-129,FR-133')

batch(6, 'test', '''
Write rendered-manifest/admission/credential-separation checks in tests/contract/test_deployment.py and opt-in effective-policy/root/write/API/pivot tests in tests/integration/test_sandbox.py; retain denied probe destinations as fixture config | FR-118,FR-119,FR-120,FR-121,FR-122,FR-135,FR-136,FR-138,NFR-009
''')
batch(6, 'implementation', '''
Create namespace, restricted worker Job template, RBAC/admission and separate lifecycle/conversation containers in deploy/base/workloads.yaml and deploy/base/rbac.yaml; Never/backoffLimit=0, no hostPath/network/privilege/token mounts or shared PID/credential namespaces | FR-002,FR-003,FR-119,FR-135
Create default-deny Cilium-enforced IP/CIDR+port policies, narrow internal selectors/DNS, internal substrate TLS and operator ingress in deploy/base/network-policy.yaml and deploy/base/services.yaml; no FQDN or automatic allowlist expansion | FR-118,FR-135,FR-136
Create single-owner Recreate/RWOP block-volume substrate manifests and operator storage/image/CIDR/identity overlay in deploy/base/storage.yaml and deploy/overlays/operator/kustomization.yaml; fail uncertain node fencing rather than force replacement | FR-117,FR-138
Implement effective-policy/additive-rule/IP-family/metadata-node, mount, admission and volume-lock/fencing preflight in src/foundry_v2/integrations/kubernetes.py; root probe requires narrow operator-provisioned exception | FR-011,FR-118,FR-119,FR-135,FR-138
Implement authoritative scope/action policy and hard-rule system prompts, safe nondisposable defaults, setup pivot warning and immediate tightening in src/foundry_v2/governance/scope.py and src/foundry_v2/roles/prompts.py | FR-050,FR-120,FR-121,FR-122,FR-147,NFR-009
Document operator inputs, TLS/Secret setup, admission exception, denied probes and uncertain-owner recovery in deploy/README.md; no real credentials or automatic live deployment | FR-120,FR-135,FR-136,FR-146
''')
add(6, 'verification', 'Run manifest tests now and authorized live root/storage/identity probes when prerequisites are supplied; record versions, denied paths and unexecuted checks in tests/acceptance/results/us6-sandbox.md', 'FR-118,FR-119,FR-135,FR-138,NFR-009')

batch(7, 'test', '''
Write all four detection technique and secret-redaction fixtures in tests/acceptance/test_us7_detection.py; assert provenance, scope, attempts and no direct publication | FR-039,FR-040,FR-041,FR-042,FR-045,FR-046,FR-047,FR-048,FR-049,FR-050,FR-051
Write five-verdict/evidence-leg/carve-out/invalid-citation/sanitizer/map-fallback tests in tests/acceptance/test_us7_triage.py; assert stored reasoning and only TP permits intent | FR-031,FR-032,FR-033,FR-034,FR-035,FR-036,FR-037,FR-038,FR-044,FR-052,FR-053,FR-054,FR-055,FR-056,FR-057,FR-058,FR-059,FR-061,FR-087,FR-088,FR-089,FR-090,FR-091
''', True)
batch(7, 'implementation', '''
Implement target-scoped structural path/symbol/weakness fingerprint and observation dedup in src/foundry_v2/governance/fingerprint.py and src/foundry_v2/substrate/findings.py; retain every verdict/reason and replace observation idempotently | FR-045,FR-047,FR-061,FR-087,FR-088,FR-093,FR-094
Implement five focused Cartographer document passes, complete persisted digests and mechanical nonempty fallback in src/foundry_v2/roles/cartographer.py; partial/absent map never blocks other ready roles | FR-031,FR-032,FR-033,FR-034,FR-035,FR-036,FR-037,FR-038
Implement pinned verbatim CodeGuard corpus reader and organization-rule overlay with rule IDs/digests in src/foundry_v2/integrations/codeguard.py; independent versioned corpus with no query-language translation | FR-039,FR-043
Implement OSV offline-snapshot lockfile and Gitleaks adapters in src/foundry_v2/integrations/scanners.py; no target installers, visible unsupported coverage and redact secret values before logs/model/storage | FR-040,FR-041,FR-045,FR-046
Implement rule sweep and exploratory Detector graphs, prefetched body/call/map context, scope, checkpoint resume and coverage-attempt logging in src/foundry_v2/roles/detector.py; prior notes remain hints and output stays internal | FR-039,FR-042,FR-046,FR-048,FR-049,FR-050,FR-051,NFR-001
Implement mechanical evaluated-commit citation resolution and three-leg structural evidence gate including narrow presence-is-vulnerability carve-out in src/foundry_v2/governance/evidence.py; failed citations demote to needs-review | FR-054,FR-055,FR-089,FR-090,FR-091
Implement open-ended fixed-checklist Triager, scoped rejection, full reasoning, optional testbed tools and exploratory rule-gap records in src/foundry_v2/roles/triager.py; no exploited mutation | FR-044,FR-052,FR-053,FR-056,FR-057,FR-058,FR-059
Implement fenced candidate/verdict endpoints and TP-only report/publication eligibility in src/foundry_v2/substrate/verdicts.py; reject missing reasoning and unauthorized state changes | FR-054,FR-055,FR-056,FR-059,FR-061,FR-087,FR-088,FR-089,FR-091
''')
add(7, 'verification', 'Run seeded mixed-technique tests and define blind human precision sample protocol/results in tests/acceptance/results/us7-precision.md; >=90% publication precision requires actual model/report pipeline later, not fixture accuracy', 'FR-054,FR-059,NFR-003')

batch(10, 'test', '''
Write self-contained report/CWE/CVSS/permalink/label/redaction and lost-response/concurrent-publisher acceptance in tests/acceptance/test_us10_reporting.py; all non-TP verdicts must remain unpublished | FR-077,FR-078,FR-079,FR-080,FR-081,FR-082,FR-085,FR-086,FR-095,FR-096,FR-137
''')
batch(10, 'implementation', '''
Implement Reporter graph and complete evidence-supported report schema/template in src/foundry_v2/roles/reporter.py and src/foundry_v2/templates/finding.md; CWE rationale, attacker prerequisites and reproduction are required | FR-077,FR-078,FR-081,FR-085
Implement CVSS 4.0 vector/score validation against official conformance vectors, evidence rationale and exact severity label tiers in src/foundry_v2/governance/severity.py | FR-079,FR-095
Implement commit-pinned encoded GitHub source links, internal-detail filtering and PoC references in src/foundry_v2/integrations/report_links.py; document reader grants without granting permissions | FR-065,FR-077,FR-085,FR-086
Implement atomic report revisions/publication outbox, unique fingerprint marker and fenced publisher ownership in src/foundry_v2/substrate/publications.py; uncertain outcome blocks additional creates | FR-080,FR-081,FR-082,FR-137
Implement secret-isolated GitHub publisher, missing-label creation/exact colors, claim-only in-progress label and paginated all-issue marker reconciliation in src/foundry_v2/integrations/github.py; explicit API version, retry read-only on ambiguity and operator resolution | FR-080,FR-082,FR-095,FR-096,FR-137
Wire report/intent endpoints and nonconfirmed-verdict withdrawal of existing issue/body/labels in src/foundry_v2/substrate/report_routes.py; never replace issue on revision | FR-081,FR-082,FR-137
''')
add(10, 'verification', 'Run report and ambiguous publication fixtures in tests/acceptance/test_us10_reporting.py; document reader-only reproduction procedure pending live US8 in tests/acceptance/results/us10-reproduction.md', 'FR-065,FR-077,FR-079,FR-086,FR-137')

batch(3, 'test', '''
Write grounded record-citation, slow-answer lane isolation and unauthorized-mutation tests in tests/acceptance/test_us3_questions.py | FR-014,FR-019,FR-020,FR-112,FR-113,FR-114,NFR-009
''')
batch(3, 'implementation', '''
Implement bounded lock-protected shared notes with no credential values, finding details or completion assertions in src/foundry_v2/substrate/notes.py; fresh sessions consume notes as advisory | FR-112,FR-113,FR-114
Implement read/query/task/steer-only conversational bridge and cited substrate answers in src/foundry_v2/orchestrator/conversation.py; isolate model sidecar from lifecycle secrets and authority | FR-014,FR-019,FR-020,NFR-009
Implement authenticated questions API and escaped cited answer UI in src/foundry_v2/api/questions.py and src/foundry_v2/templates/questions.html; async answer cannot block status, drains or monitoring | FR-014,FR-020
''')
add(3, 'verification', 'Run known-verdict question, adversarial notes and long-answer tests in tests/acceptance/test_us3_questions.py with simultaneous lifecycle activity', 'FR-014,FR-019,FR-020,FR-114')

batch(8, 'test', '''
Write clean-room access isolation, success/partial/failure/prohibited/no-testbed and attempt-limit acceptance in tests/acceptance/test_us8_validation.py | FR-062,FR-063,FR-064,FR-065,FR-066,FR-067,FR-068,FR-092
''')
batch(8, 'implementation', '''
Implement Validator artifact-author graph with self-contained prerequisites/Authorized testing only header and bounded attempts in src/foundry_v2/roles/validator_author.py; every TP is eligible regardless of Triager hint | FR-062,FR-065,FR-067
Implement lifecycle-requested fresh reproducer session and graph receiving only claim/report/artifact, structured observed-impact outcomes and testbed scope checks in src/foundry_v2/roles/validator_reproduce.py; no author checkpoint access | FR-062,FR-063,FR-064,FR-066
Implement fenced validation persistence, independent-author checks and exploited flag gate in src/foundry_v2/substrate/validation.py; failure preserves TP, absent testbed records unexecuted/no-testbed | FR-063,FR-064,FR-068,FR-092
Wire validated PoC blob/report revision updates into existing Reporter pipeline in src/foundry_v2/integrations/validation_reports.py; no-testbed artifact never implies demonstrated impact | FR-065,FR-068,FR-082,FR-092
''')
add(8, 'verification', 'Run fixture validation plus authorized disposable-testbed and independent human artifact-only reproduction in tests/acceptance/test_us8_validation.py and tests/acceptance/results/us8-impact.md; record live checks unavailable as unexecuted', 'FR-062,FR-063,FR-065,FR-066,FR-068,FR-092')

batch(9, 'test', '''
Write zero-finding component, severity/exploitation order and original-goal attempt rollup tests in tests/acceptance/test_us9_rollup.py | FR-083,FR-084
''')
batch(9, 'implementation', '''
Implement complete component membership, counts/coverage-evidence rollup projection in src/foundry_v2/substrate/rollups.py; preserve zero findings and unresolved component assignments explicitly | FR-083
Implement evaluation rollup template/publication through Reporter, evidence-supported priority and no unsupported chains/keystone fixes in src/foundry_v2/templates/rollup.md and src/foundry_v2/integrations/rollup_reports.py | FR-083,FR-084,FR-085
''')
add(9, 'verification', 'Run rollup fixtures and compare reported coverage to persisted goals revision in tests/acceptance/test_us9_rollup.py', 'FR-083,FR-084')

batch(11, 'test', '''
Write unchanged/line-shift/path-renamed rerun and inherited-verdict/withdrawal/crash tests in tests/acceptance/test_us11_rerun.py | FR-027,FR-060,FR-061,FR-093,FR-094,FR-117,FR-137,NFR-001,NFR-002
''')
batch(11, 'implementation', '''
Implement changed-file hash reuse and call-edge patching under staged generation switch in src/foundry_v2/indexing/incremental.py; stale/deleted edges disappear only with complete new generation | FR-027,FR-026,FR-117,NFR-001,NFR-002
Implement scoped cross-run verdict reuse, retained non-TP reasoning and fresh TP investigation priors in src/foundry_v2/substrate/inheritance.py; stable fingerprint excludes lines/snippets/time | FR-060,FR-061,FR-088,FR-093,FR-094
Wire rerun/resume with preserved ledger/checkpoints and original issue identity in src/foundry_v2/orchestrator/resume.py; apply changed verdict withdrawal through publication outbox | FR-012,FR-082,FR-137,FR-138,NFR-001,NFR-002
''')
add(11, 'verification', 'Run two complete deterministic fixture evaluations and shifted-line edit in tests/acceptance/test_us11_rerun.py; assert zero new findings/issues and changed-file parse counts', 'FR-027,FR-060,FR-093,FR-094,NFR-002')

batch(12, 'test', '''
Write next-cycle priority task, idle/immediate steering, peer-origin, help-request dedup, interactive turn and override acceptance in tests/acceptance/test_us12_steering.py | FR-015,FR-016,FR-017,FR-018,FR-019,FR-101,FR-102,FR-106,FR-109,FR-111,NFR-008
''')
batch(12, 'implementation', '''
Implement operator/agent task add/edit/reprioritize/close APIs and follow-on-work tools in src/foundry_v2/api/tasks.py and src/foundry_v2/workers/task_tools.py; IDs never equal priority position, agents queue leads without abandoning held work | FR-015,FR-097,FR-101,FR-102,FR-103
Implement durable origin-tagged peer/idle/immediate steer delivery, graph cancellation/checkpoint handoff and operator-message replies in src/foundry_v2/workers/steering.py and src/foundry_v2/api/steering.py; peers cannot delegate authority | FR-017,FR-106,FR-109,FR-111
Implement authenticated turn-by-turn single-agent session with sandboxed role tools in src/foundry_v2/api/interactive.py; retain claims/checkpoints, scoped credentials and operator authority | FR-018,FR-136
Implement GitHub operator help-request recognition, authenticated author authorization, task resolution comment/marker clearing with durable side-effect identity in src/foundry_v2/integrations/help_requests.py; untrusted issue text alone grants no authority | FR-016,NFR-002,NFR-009
Implement explicit verdict/exploited/coverage/auto-stop override audit and publication reconciliation in src/foundry_v2/api/overrides.py; conversation alone cannot override and preserve original automated provenance | FR-019,NFR-008
''')
add(12, 'verification', 'Run steering/override/help-request tests in tests/acceptance/test_us12_steering.py including unauthenticated/agent-origin rejection and interrupted healthy claim handoff', 'FR-015,FR-016,FR-017,FR-019,FR-106,NFR-008,NFR-009')

batch(13, 'test', '''
Write adapter substitution contract suite in tests/contract/test_role_bindings.py for fake provider/tracker/substrate/deployment plus clock/index ports | NFR-003,NFR-004
''')
batch(13, 'implementation', '''
Add explicit adapter composition/factory and remove accidental concrete binding imports from roles in src/foundry_v2/integrations/bindings.py; preserve existing selected production adapters | NFR-003
Document versioned integration ports and build alternate in-memory test adapters in docs/integration-contracts.md and tests/fixtures/adapters.py; no extra production integrations | NFR-003,NFR-004
''')
add(13, 'verification', 'Run all eight role contracts against both selected mocked and alternate fake adapters in tests/contract/test_role_bindings.py with no role behavior edits', 'NFR-003,NFR-004')

batch(14, 'test', '''
Write pinned corpus/org additions/unchanged external-load and rule-gap provenance tests in tests/acceptance/test_us14_corpus.py | FR-043,FR-044
''')
batch(14, 'implementation', '''
Document independent Git corpus pin/update review, organization additions and reproducible export manifest in rules/README.md and src/foundry_v2/integrations/corpus_export.py; retain verbatim rule content | FR-043
Build standalone compatible consumer example in examples/rule_consumer.py and operator-review rule-gap export in src/foundry_v2/integrations/rule_gap_export.py; no automated Self-Improver | FR-043,FR-044
''')
add(14, 'verification', 'Run actual standalone consumer load with digest comparison in tests/acceptance/test_us14_corpus.py; verify exported rule gaps trace to confirmed exploratory findings', 'FR-043,FR-044')

batch('Polish', 'test', '''
Implement all-41-operation auth/idempotency/CAS/error/response-schema contract collection in tests/contract/test_openapi_coverage.py; add any missing routes without weakening runtime.md | FR-136,NFR-003
Implement cross-stage kill/restart and transactional fault campaigns in tests/integration/test_crash_recovery.py; slow heartbeating workers keep claims, dead claims recover within stale threshold plus one cycle, backups restore all referenced blobs | FR-006,FR-098,FR-099,FR-104,FR-105,FR-117,FR-138,NFR-001,NFR-007
Implement integration-outage and target prompt-injection campaigns in tests/integration/test_degradation.py; verify no privilege/authority gains, shared backpressure and unaffected work | FR-115,FR-116,FR-135,FR-144,NFR-004,NFR-009
Implement equivalent-target fleet-size token/spend comparison and duplicate-work assertions in tests/integration/test_cost_scaling.py; report disproportionate growth without inventing throughput targets | NFR-005
''', True)
batch('Polish', 'implementation', '''
Reduce duplicate provider work through atomic work claims, cached immutable context and completed-checkpoint reuse in src/foundry_v2/workers/context_cache.py; use cost campaign evidence and preserve provider backpressure semantics | NFR-005
Reconcile contract surface extensions required by interactive/help/override/publication resolution tools and implemented schemas in specs/001-foundry/contracts/openapi.json and docs/integration-contracts.md; retain fixed role boundaries and document compatible changes | NFR-003
Write operator runbook for preflight, Secret inputs, cap reset, ambiguous publication resolution, policy tightening, backup/restore, reader grants and stopping fixtures in docs/operator-guide.md and README.md | FR-012,FR-120,FR-137,FR-146,NFR-007
''')
batch('Polish', 'verification', '''
Collect every FR/NFR positive/prohibited fixture into tests/acceptance/requirements.json using task-coverage.md; fail on unmapped or uncollected obligations, run deterministic suite and record results in tests/acceptance/results/structural.md | NFR-003
Run quickstart end-to-end SC-001 through SC-009 with authorized cluster/GPU/GitHub/testbed inputs and reconstruct full publication provenance in tests/acceptance/test_end_to_end.py and tests/acceptance/results/release.md; require quality/human reproduction, zero rerun duplicates and bounded reclamation | NFR-001,NFR-002,NFR-006
Record all 11 constitution gates, live versions/model digest/corpus pins, skipped checks, backup hashes and go/no-go decision in tests/acceptance/results/release.md; live deployment/publication needs deployment authorization and unavailable evidence cannot count as pass | FR-118,FR-138,NFR-006
''')

def refs_of(row):
    return row['refs'].split(',') if row['refs'] else []

dependencies = {1: [], 2: [1], 4: [1], 5: [1,4], 6: [1], 7: [1], 10: [7],
                3: [2,7], 8: [7,10,6], 9: [4,7,10], 11: [1,7,10],
                12: [1,2,3], 13: [1,7,10], 14: [7]}
groups = ['Setup','Foundation',*stories,'Polish']
header = '''# Tasks: Foundry-v2

**Input**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts](contracts/README.md), [quickstart.md](quickstart.md), unchanged constitution v0.2.0.
**Date**: 2026-10-10 | **Branch**: main | **Status**: generated backlog; no implementation or live checks executed.

Tasks follow the template's Setup → Foundation → prioritized stories → Polish structure. Stories retain their original spec IDs; all P1 phases precede P2/P3 phases. Spec §3.4 and §1.6 explicitly require acceptance testing, so meaningful contract/fault/acceptance tasks are included. Write listed tests before their implementations, establish expected failures, then rerun at the phase checkpoint. Test authoring is distinct from the verification tasks that require them to pass.

All paths are repository-relative implementation targets, including files that do not yet exist. `[US1]` maps to spec `US-1`, etc. `[P]` means independent file sets within that phase's test-authoring wave after prerequisites; it never bypasses phase or implementation dependencies. Within each phase execute unmarked tasks in order. Read each linked design artifact and its referenced requirements before implementing; [task-coverage.md](task-coverage.md) maps every FR/NFR to implementation and verification task IDs.

One role is not an additional process identity: Orchestrator has isolated deterministic and conversational lanes; Validator has separate author/fresh-reproducer sessions. Keep all eight core roles and defer all five extension roles, vector search, other production providers/trackers and compliance mapping. Missing operator deployment inputs block live preflight; do not invent credentials, CIDRs, rates, identity groups or storage support.

'''
parts = [header]
for phase, group in enumerate(groups, 1):
    if isinstance(group,int):
        title,priority,criteria = stories[group]
        parts += [f'## Phase {phase}: US-{group} — {title} ({priority})\n',
                  f'**Goal / independent acceptance**: {criteria}\n',
                  '**Prerequisites**: Foundation' + ''.join(f', US-{d}' for d in dependencies[group]) + '. Adjacent stages can use fixed fixtures for independent acceptance; complete system acceptance requires real bindings.\n']
    else:
        parts += [f'## Phase {phase}: {group}\n', {'Setup':'Initialize package, locked runtime and deterministic fixtures.', 'Foundation':'Blocking shared persistence, identity, liveness and contracts. All stories require this checkpoint.', 'Polish':'Integrate every story and collect production-readiness evidence.'}[group]+'\n']
    current_kind = None
    for row in [r for r in rows if r['group']==group]:
        if row['kind'] != current_kind:
            current_kind = row['kind']
            parts.append(f'### {current_kind.capitalize()} tasks\n')
        labels = (' [P]' if row['parallel'] else '') + (f' [US{group}]' if isinstance(group,int) else '')
        task_line = f"- [ ] {row['id']}{labels} {row['text']}. ({row['refs'].replace(',', ', ')})"
        if task_line in prior_completed:
            task_line = task_line.replace('- [ ]', '- [X]', 1)
        parts.append(task_line)
    parts.append('\n**Checkpoint**: All phase verification tasks pass against stated fixtures; record live prerequisites/unexecuted evidence explicitly.\n')

parts += ['''## Dependencies and execution order

Setup → Foundation → user-story phases → Polish. Phase order is the conservative executable sequence. Edges below are the minimum integrated prerequisite graph; independent acceptance can use adjacent-stage fixtures as stated above.

```mermaid
flowchart TD
  Setup --> Foundation
''']
for group in stories:
    if not dependencies[group]:
        parts.append(f'  Foundation --> US{group}')
    for dep in dependencies[group]:
        parts.append(f'  US{dep} --> US{group}')
parts += ['  US5 --> Polish\n  US6 --> Polish\n  US8 --> Polish\n  US9 --> Polish\n  US11 --> Polish\n  US12 --> Polish\n  US13 --> Polish\n  US14 --> Polish\n  Polish --> FullAcceptance\n```\n',
'''US4 uses a fixture ledger until US5 binds actual accounting. US1 demonstrates lifecycle startup using role doubles until production graphs are delivered; installing/running an actual fleet additionally requires US5 budget safeguards and US6 boundary enforcement. US10 tests report assembly with fixed validation input; live exploited reproduction is delivered by US8. US7's precision gate runs on real model outputs only in full acceptance. These are incremental acceptance boundaries, not production-completion claims.

### Parallel execution examples

Foundation checkpoint tests can be authored together, then implementations proceed sequentially. US1 parser/startup tests and US7 detector/triage tests have disjoint files and are marked `[P]`. Final fault, outage, cost and API suites can be authored together after all stories. Sequential same-file updates always wait for earlier tasks.
''']
for group in stories:
    test_rows = [r for r in rows if r['group']==group and r['kind']=='test']
    if len(test_rows)>1:
        example = f"Author {test_rows[0]['id']} and {test_rows[1]['id']} together after prerequisites; run their verification after implementations."
    else:
        example = f"Author {test_rows[0]['id']} alongside independent story test authoring after that story's prerequisites; implementations within US-{group} stay sequential."
    parts.append(f'- **US-{group}**: {example}')
parts += ['''
## Implementation strategy

1. Deliver Setup + Foundation + US1 as the first lifecycle/index MVP using deterministic role/provider/policy doubles. This is a development slice, not an autonomous security evaluation ready to deploy.
2. Add US2 visibility, US4/US5 coverage/accounting and US6 effective sandbox. Before any actual fleet run require these safeguards plus authenticated control and successful deployment preflight.
3. Add US7 evidence-gated detection/triage and US10 reporting for an end-to-end source-only evaluation. Complete the P2 validation/rollup/rerun/operator stories and P3 integration/corpus stories incrementally; each phase reruns its independent acceptance criteria.
4. Run full quickstart, every requirement fixture and SC-001–SC-009. Production readiness requires actual model quality, authorized sandbox/storage probes and human PoC reproduction; mocked tests cannot prove them. Obtain deployment authorization when needed, after rendering/reviewing concrete artifacts.

Do not mark a task complete for a stub, unexecuted test or placeholder deployment input. Commit logical completed increments without credentials. A narrower MVP never removes remaining requirements from the backlog.
''']

spec = (FEATURE/'spec.md').read_text(encoding='utf-8')
required = sorted(set(re.findall(r'^- \*\*((?:FR|NFR)-\d{3})', spec, re.M)))
coverage = {}
for req in required:
    impl = [r['id'] for r in rows if req in refs_of(r) and r['kind']=='implementation']
    checks = [r['id'] for r in rows if req in refs_of(r) and r['kind'] in ('test','verification')]
    coverage[req] = {'implementation':impl, 'verification':checks}

for req in required:
    if not coverage[req]['verification']:
        raise ValueError(f'Missing specific verification for {req}')
    if not coverage[req]['implementation']:
        raise ValueError(f'Missing implementation for {req}')

counts = Counter(r['group'] for r in rows)
parts += ['## Backlog summary\n', '| Phase/story | Tasks |\n|---|---|']
for g in groups:
    parts.append(f"| {'US-'+str(g) if isinstance(g,int) else g} | {counts[g]} |")
parts.append(f"\n**Total**: {len(rows)} tasks; {sum(r['parallel'] for r in rows)} explicitly parallel tasks; 149 FR and 9 NFR mapped.\n")
(FEATURE/'tasks.md').write_text('\n'.join(parts), encoding='utf-8')
cover = ['# Task coverage: Foundry-v2\n', 'This maps DRAFT v0.2.0 requirement IDs to implementation and test/verification tasks. It is planning traceability, not proof of executed software. The final requirement collector expands every mapped requirement into positive/prohibited fixtures from acceptance-coverage.md.\n', '| Requirement | Implementation | Test / verification |\n|---|---|---|']
for req, entries in coverage.items():
    cover.append(f"| {req} | {', '.join(entries['implementation'])} | {', '.join(entries['verification'])} |")
cover += ['\n## Success criteria\n', '| Criterion | Story/campaign proof |\n|---|---|',
          '| SC-001 | US1 + US7 + US10 real-model seeded end-to-end publication |',
          '| SC-002 | US7 blind human-reviewed publication precision >=90% |',
          '| SC-003 | US8 + US10 independent human PoC headline-impact reproduction |',
          '| SC-004 | Foundation + final crash campaign, stale interval plus one cycle |',
          '| SC-005 | US11 unchanged and shifted-line complete reruns |',
          '| SC-006 | US4 + US5 + final end-to-end with both hard caps unset |',
          '| SC-007 | US6 authorized container-root effective sandbox probe |',
          '| SC-008 | US2 identical status/dashboard substrate snapshot |',
          '| SC-009 | US2 + final full detector-to-report transcript reconstruction |',
          '\n## Constitution enforcement\n', '| Principle | Enforcing tasks by area |\n|---|---|',
          '| I Evidence | US7 mechanical citations and evidence-leg gate |',
          '| II Survivors | US7 verdict gating; US10 publication gate |',
          '| III Heartbeats | Foundation receipt-clock reaper; US5 rotation; final crash/slow-call campaign |',
          '| IV Claims | Foundation atomic generation claims; final race/kill campaign |',
          '| V Provider | US5 shared adaptive 429/503 and no guessed cap |',
          '| VI Coverage | US4 conjunction and goals revisions; US5 actual ledger |',
          '| VII Exploited | US8 fresh-thread author separation and observed headline impact |',
          '| VIII Fingerprints | US7 identity function; US11 shifted-line rerun |',
          '| IX Sandbox | US6 admission/policy/root probes and credential isolation |',
          '| X Authority | US3 read-only conversation; US12 origin/overrides; adversarial campaign |',
          '| XI Persistence | Foundation WAL/owner/blobs/checkpoints; US11 atomic index; crash/backup campaign |']
operation_owners = {
    'startEvaluation':'authenticated start/control/config', 'getStatus':'owner-consistent fleet',
    'controlEvaluation':'authenticated start/control/config', 'updateConfiguration':'atomic config revisions',
    'askQuestion':'authenticated questions API', 'queueTask':'operator/agent task',
    'listTasks':'operator/agent task', 'editTask':'operator/agent task',
    'steerWorker':'durable origin-tagged', 'recordOverride':'explicit verdict/exploited',
    'listFindings':'fenced candidate/verdict', 'ackMessage':'nonblocking typed operator messages',
    'streamEvents':'filtered SSE', 'registerSession':'substrate HTTP client',
    'heartbeat':'receipt-clock heartbeats', 'readSubstrateSnapshot':'owner-consistent fleet',
    'submitTask':'stable-ID named queues', 'readTasks':'stable-ID named queues',
    'updateTask':'stable-ID named queues', 'claimWork':'stable-ID named queues',
    'writeClaimedWork':'stable-ID named queues', 'submitCandidate':'structural path/symbol',
    'readFindings':'structural path/symbol', 'assignVerdict':'fenced candidate/verdict',
    'recordValidation':'fenced validation persistence', 'commitReport':'report/intent endpoints',
    'readGenerations':'substrate HTTP client', 'commitGeneration':'function/body/caller',
    'queryIndex':'function/body/caller', 'writeCoverage':'append-only attempt matching',
    'postMessage':'nonblocking typed operator messages', 'recordModelCall':'durable model-call',
    'observeBackpressure':'durable model-call', 'requestPublication':'report/intent endpoints',
    'listCheckpoints':'owner checkpoint tuple', 'deleteCheckpointThread':'owner checkpoint tuple',
    'getCheckpoint':'owner checkpoint tuple', 'putCheckpoint':'owner checkpoint tuple',
    'putCheckpointWrites':'owner checkpoint tuple', 'writeBlob':'immutable SHA-256 staging',
    'readBlob':'immutable SHA-256 staging'}
api = json.loads((FEATURE/'contracts/openapi.json').read_text(encoding='utf-8'))
cover += ['\n## API operation ownership\n', 'Every operation also runs the all-operation auth/schema/idempotency contract campaign.\n', '| Operation | Implementation task |\n|---|---|']
operations = []
for path, item in api['paths'].items():
    for method, operation in item.items():
        if method not in ('get','post','put','patch','delete'):
            continue
        op = operation['operationId']
        owner = next(r['id'] for r in rows if r['kind']=='implementation' and operation_owners[op] in r['text'])
        operations.append({'operation':op, 'task':owner})
        cover.append(f'| {op} | {owner} |')
(FEATURE/'task-coverage.md').write_text('\n'.join(cover)+'\n', encoding='utf-8')
(FEATURE/'task-metadata.json').write_text(json.dumps({'tasks':rows,'coverage':coverage,'dependencies':dependencies,'operations':operations},indent=2)+'\n',encoding='utf-8')
print(json.dumps({'total':len(rows),'counts':dict(counts),'parallel':sum(r['parallel'] for r in rows),'requirements':len(coverage)},indent=2))
