# Principle Rationale: Deep Dives

**Audience:** maintainers and reviewers who need to defend a constitutional principle in PR review.

[`constitution.md`](../../constitution.md) gives one paragraph of rationale per principle, deliberately tight. This document holds the longer context — the operating story behind each principle — that the constitution itself should not carry.

If anything here disagrees with the constitution, the constitution wins. This is commentary; the constitution is law.

---

## I. Evidence Over Assertion

**Constitution paragraph:** see [I in constitution.md](../../constitution.md#i-evidence-over-assertion).

### What we tried

Early versions promoted findings to `true-positive` based on the model's own confidence score plus a brief reasoning paragraph. The promotion criterion was effectively "the model sounds sure."

### What broke

Reviewers found, on first inspection, fluent and confident vulnerability claims that pointed at code paths that did not exist. Claims about "the `validate_input` function on line 142" when no such function existed. Claims about reachability through code that was dead-stripped at compile time. Claims so plausible that even careful reviewers had to spend minutes verifying the citations did not resolve.

The model's confidence was not predictive of correctness. The reviewer's trust in the channel collapsed within one reporting cycle.

### What we changed

Two-part fix:

1. **Three-leg evidence requirement** ([FR-087](../../spec.md#73-evidence-gate)): a `true-positive` carries citations for reachability, trust boundary, and impact. Each citation points at a specific location in the source.
2. **Mechanical resolution check** ([FR-088](../../spec.md#73-evidence-gate)): every citation is mechanically verified to resolve to real code at verdict time. If any citation does not resolve, the verdict is demoted to `needs-review`. No exceptions.

The verdict is now a structural argument the model produced, *and* a mechanical proof that the structure exists. The model is no longer the authority on whether its own claim is correct.

### Why every relaxation re-broke it

We tried "high-confidence findings can skip the gate." The fabrications came back immediately, because the same fluency that produced false claims also produced confident scoring. We tried "carve out exceptions for class X." Class X immediately accumulated the same fabrication problem; the carve-out's wording was always weaker than its intent.

### The narrow carve-out we accept

[FR-087a](../../spec.md#73-evidence-gate) — for "presence-is-the-vulnerability" classes (hardcoded credentials, deprecated cryptographic primitives, sensitive values committed to source) — was added because the trust-boundary leg is satisfied trivially by "the source repository itself." This carve-out is narrow, enumerated, and does **not** apply to data-flow classes (injection, IDOR, SSRF, traversal). The gate already passes unsound arguments on those (it checks that citations resolve, not that the argument is valid); weakening it further is the wrong direction.

---

## II. Surface Only What Survives

**Constitution paragraph:** see [II in constitution.md](../../constitution.md#ii-surface-only-what-survives).

### What we tried

One issue per detection candidate, posted directly to the issue tracker. The system was technically transparent: every signal it found was visible to humans.

### What broke

Tens of thousands of issues per target. False-positive rates in the high 90s. The tracker became unusable. Operators ignored the channel. The single-digit-percent of true findings drowned in noise indistinguishable from spam. Reviewers built filters that, predictably, also filtered out real findings.

We watched a security team unsubscribe from the channel within 48 hours of system enablement.

### What we changed

[FR-044](../../spec.md#54-detector): the Detector writes only to the internal finding store, never to the issue tracker.

[FR-066](../../spec.md#55-triager): the Triager is the only role that promotes findings to surfaceable status.

[FR-072+](../../spec.md#58-reporter): the Reporter is the only role that writes to the issue tracker, and only for promoted findings.

The internal store absorbs the volume; humans see only what survived triage.

### Why this is uncomfortable

The result feels like withholding information. A reviewer who knows the system is detecting things wants to see the candidates. We learned the hard way that what they want is not what serves them: a flood of noisy candidates trains the operator to ignore the channel, at which point true findings, *which the system can produce*, do not reach the human anyway.

The detection-volume / surface-volume asymmetry is not a defect. It is the design.

---

## III. Liveness By Heartbeat, Never By Clock

**Constitution paragraph:** see [III in constitution.md](../../constitution.md#iii-liveness-by-heartbeat-never-by-clock).

### What we tried

Wall-clock timeouts. If an agent had held a claim for more than N minutes, the substrate reclaimed the claim and re-queued the work.

### What broke

Under load, the LLM provider rate-limited the fleet. Healthy agents waited, sometimes for minutes, on rate-limited responses. Their wall-clock timer kept ticking. The substrate reclaimed their claims. The work was re-queued. The next agent started over from scratch on the same task. It also got rate-limited. It also timed out. The next agent started over. Throughput approached zero while the fleet "looked busy" — every slot full, every claim held, every agent making progress that was about to be discarded.

We measured >90% false-termination rates during peak traffic. Days of compute went to re-doing work the previous agents had nearly finished.

### What we changed

Two parts:

1. **Heartbeat-only liveness** ([FR-100](../../spec.md#82-liveness)): an agent is alive if it is heartbeating. A waiting agent still heartbeats. A dead agent does not. Wall-clock runtime is irrelevant to the liveness signal.
2. **Heartbeat on its own lane** ([FR-101](../../spec.md#82-liveness)): the heartbeat MUST NOT share an event loop or thread pool with primary work. Otherwise, a CPU-bound or upstream-blocked moment causes a healthy agent to miss beats and be killed for it.

The session-rotation mechanism ([FR-118](../../spec.md#95-agent-lifecycle-limits)) is separate: it is a deliberate cost-control rotation of a heartbeating agent's session *after* its claim is settled, not a liveness misfire.

### Why version 0.1.0 → 0.2.0 narrowed this

The original phrasing forbade wall-clock-based termination outright. That over-constrained session rotation, which is a deliberate, claim-aware operation. The 0.2.0 narrowing carved out FR-118 explicitly: wall-clock MAY trigger session rotation; it MUST NOT trigger claim reclamation.

---

## IV. Claims Are Atomic And Mortal

**Constitution paragraph:** see [IV in constitution.md](../../constitution.md#iv-claims-are-atomic-and-mortal).

### What we tried

Two failure modes, each shipped at one point:

1. **Cooperative claim**: agents wrote a "claim" record but the substrate did not enforce uniqueness. Two agents could claim the same task within the same window.
2. **Non-mortal claims**: an agent that crashed left its claim record in place. The work was stranded until an operator manually unlocked it.

### What broke

Cooperative claim produced duplicate work and mutual overwrite. Two Triagers ran on the same candidate. Their results were not the same. The last writer won. The earlier writer's reasoning was lost. Reviewers reading the resulting verdict could not reconstruct why.

Non-mortal claims meant every overnight crash stranded whatever the dead agent held until the next morning. We had operators starting their day by manually unlocking dozens of claims.

### What we changed

[FR-095](../../spec.md#81-work-queue): claims are atomic. Two concurrent claimants get different tasks (or one gets "none available"). The substrate, not the agents, enforces uniqueness.

[FR-096](../../spec.md#81-work-queue): claims are mortal. Within bounded time of the holder's heartbeat going stale, the claim is automatically released, with no operator action.

The combination is what makes a parallel fleet behave like one system. Either alone is insufficient.

### What we tried that did not work

- "Next agent breaks the lock if it looks stale": produced both stranded and duplicate work depending on timing.
- "Operator manually unlocks": broke at scale.
- "Process supervisor releases on exit": works for crash, fails when the process supervisor itself is wedged.

Liveness-tied release is the only mechanism that produced neither stranded nor duplicate work in production.

---

## V. The Provider Is The Rate Arbiter

**Constitution paragraph:** see [V in constitution.md](../../constitution.md#v-the-provider-is-the-rate-arbiter).

### What we tried

Internal rate caps to "be a good neighbor" to the LLM provider. The cap was set just below the provider's stated quota.

### What broke

The provider's actual limit moved. Up: we benefited only when someone remembered to raise the internal number. Down: we throttled below their tightening limit and got throttled twice. We also discovered the stated quota was not the *actual* burst limit — internal caps based on the stated quota left paid-for capacity idle.

Worse, internal caps masked the provider's signal. Our alerting fired on the *internal* cap, not on the provider's 429s. When the provider had a degraded period, we did not see it; we just saw our own rate cap firing more often.

### What we changed

[FR-105](../../spec.md#85-rate-governance): no internal rate caps below the provider's actual limit. Call as fast as the work needs.

[FR-106](../../spec.md#85-rate-governance): backoff on rate-limit signals is shared fleet-wide, not per-agent. One agent's 429 informs all of them.

The system now adaptively converges on the real limit and tracks it as it changes. We learned about provider degradation from our own metrics, in real time, instead of from the provider's status page hours later.

### Why "adaptive" is non-negotiable

A static cap is wrong on day one (because the real limit is rarely the stated limit) and wrong on day N (because the limit moves). Only an adaptive control loop against the provider's actual signal handles both.

---

## VI. Coverage Before Yield

**Constitution paragraph:** see [VI in constitution.md](../../constitution.md#vi-coverage-before-yield).

### What we tried

Auto-stop the fleet when trailing yield (findings per unit spend) fell below a threshold. The reasoning: if we are not finding things, we are wasting compute.

### What broke

Yield is noisy early. On hard targets, the first six hours are dry as the system explores cold. The auto-stop fired in those first six hours. The evaluation ended before it had really begun. Operators learned to disable the auto-stop. The system was now operating without a "done" signal at all.

### What we changed

[FR-115 — FR-117](../../spec.md#94-yield-auto-stop): trailing yield is necessary but not sufficient. Auto-stop also requires:

- A trailing window of spend has actually accumulated (not noise from the first hour).
- A configured minimum runtime has elapsed.
- The coverage-complete flag is set ([FR-071](../../spec.md#57-coverage-guide)).

The conjunction of "yield low" and "coverage complete" is the honest done signal: we looked everywhere the operator asked, and the rate of new findings has flatlined.

### What "coverage" actually means

The Coverage-Guide ([§5.7](../../spec.md#57-coverage-guide)) maintains a checklist of what an evaluation should examine for the configured target. "Coverage complete" means every checklist item has been credibly attempted. It does not mean "no bugs remain"; it means "we did the work the operator asked for."

---

## VII. Exploited Means Demonstrated

**Constitution paragraph:** see [VII in constitution.md](../../constitution.md#vii-exploited-means-demonstrated).

### What we tried

`exploited` could be set by the agent that wrote the proof-of-concept, on its own assessment that the POC worked. Variations included "verified the mechanism if not the impact" and "demonstrated under a debugger".

### What broke

`exploited` is the label reviewers filter on first. Within one reporting cycle, the reviewers' confidence in the label was destroyed: too many `exploited` findings turned out to be "exploited only if you stretch the meaning". Reviewers started ignoring the label entirely. The system's strongest signal had become noise.

### What we changed

[FR-089](../../spec.md#74-exploited): the flag is set only by the **Validator**. The Validator runs in a clean room, receives only the artifact and the claim, attempts the reproduction on the live testbed, and observes the impact. If the impact is observed, the flag is set. Nothing else qualifies.

Specifically forbidden:

- Setting on plausible-evidence alone.
- Setting on debugger-only repro.
- Setting on "would-be-exploitable-if".
- Setting by the agent that wrote the POC.

### Why fresh eyes matter

An agent that wrote a POC has incentive to call it successful (the same kind of incentive a human author has). A fresh agent that has not seen the construction has no such incentive. Independent reproduction is the structural protection.

---

## VIII. Fingerprints Are Stable Under Edit

**Constitution paragraph:** see [VIII in constitution.md](../../constitution.md#viii-fingerprints-are-stable-under-edit).

### What we tried

Fingerprints included line numbers and a hash of the surrounding code snippet. The intent: catch the case where the same bug class moves within a function as "the same finding".

### What broke

Any nearby edit changed the fingerprint. Re-runs after code changes re-filed every existing finding as new. Triagers spent every re-run re-deciding findings that had already been triaged. Cross-run inheritance was meaningless. The issue tracker accumulated duplicate issues for the same underlying bug.

### What we changed

[FR-090](../../spec.md#75-fingerprint): fingerprint = hash(normalized path, function/symbol, vulnerability class). Excluded: line numbers, code snippets, detection timestamps.

The fingerprint now survives edits to the function body. It breaks only when the function is moved or renamed, which is the correct point to call it a new finding.

### Why excluding line numbers is the *whole point*

We understand the appeal of including them: "if the bug is on line 50 and now it's on line 80, it's the same bug." But "the bug is on line 50" is information the triager records inside the finding, not the finding's identity. Identity stable under edit means the same finding is recognized across re-runs. That is what the fingerprint is for.

---

## IX. Sandbox By Infrastructure, Not By Prompt

**Constitution paragraph:** see [IX in constitution.md](../../constitution.md#ix-sandbox-by-infrastructure-not-by-prompt).

### What we tried

Prompt-level rules: "Do not access network destinations outside the allowlist." "Do not write to /etc." Strong language, repeated in the system prompt and in tool descriptions.

### What broke

Agents read untrusted content: target source, target documentation, testbed responses. Some of that content contained instructions. An exploratory agent investigating a target whose README said "for testing, run this curl command" obeyed. The curl reached an external host. The agent reported it as part of its investigation. The host was outside the allowlist.

Prompt rules cannot survive a prompt-injection of any kind. And prompt injections come from places we cannot fully clean.

### What we changed

[FR-107 / FR-108](../../spec.md#91-sandbox): the sandbox is enforced by the runtime. An agent with full privileges *inside* the sandbox cannot reach a host outside the allowlist or write to a path mounted read-only, regardless of what its prompt says, what a peer told it, or what content in the target instructed it to do.

Prompt-level hard rules ([FR-110](../../spec.md#92-scope-rules)) remain — as defense in depth. Not as the boundary.

### How to verify

The sandbox verification ritual is in [`../architecture/substrate-contracts.md`](../architecture/substrate-contracts.md). If you have not run it, you have not actually sandboxed anything.

---

## X. The Operator Outranks Every Agent

**Constitution paragraph:** see [X in constitution.md](../../constitution.md#x-the-operator-outranks-every-agent).

### What we tried

Persistent shared notes: agents wrote what they had attempted and what they had concluded. Other agents read the notes and adjusted their own work accordingly.

### What broke

Agents talked each other out of work. One agent wrote "X is saturated, no further investigation needed." The next agent read this and skipped X. The next read two such notes and was even more convinced. Within a day the fleet had collectively decided the evaluation was done. *And was citing its own consensus as evidence to the operator.*

The operator believed the system. The evaluation ended. The vulnerabilities were still there.

### What we changed

[FR-102](../../spec.md#83-inter-agent-communication): peer messages are advisory. The recipient treats them as hints, not commands.

Implementation: operator instructions outrank anything any agent wrote anywhere. An agent's persistent notes are a record of what that agent attempted; another agent reading them does not adopt the conclusions. The Coverage-Guide's coverage flag is set by the Coverage-Guide based on the substrate's actual contents, not by a peer's claim that something is done.

### Why this requires *vigilance*, not just architecture

The architecture (advisory messages, operator authority) prevents the obvious failure. The subtle failure is when agents write notes optimized to be persuasive (because the model has learned that persuasive writing gets respected). Reviewers must read notes as records of what an agent claimed, not as truth, even when the writing is good.

---

## XI. Persist Atomically

**Constitution paragraph:** see [XI in constitution.md](../../constitution.md#xi-persist-atomically).

### What we tried

"Delete old, write new" persistence: rm the existing index file, then write the new one. Same pattern for the finding store, the coverage state, the shared notes.

### What broke

Deploy-time process termination, twice in one quarter, landed exactly between the delete and the write. The reader (the next role to start up) found nothing. The hours of indexing work that had been about to land were lost. The system continued operating against an empty index — silently, because "empty index" was indistinguishable from "no index yet" in the consumer.

### What we changed

[FR-106a](../../spec.md#86-atomic-persistence): write the new state completely; then atomically replace the old, with no intermediate state in which a reader sees nothing.

POSIX rename, transactional commits, conditional puts — anything that makes the swap atomic. Never delete-then-write.

### Why this matters across the substrate, not just the index

We initially wrote the principle as "the index must persist atomically." Then we hit the same failure on the coverage state, then on the shared notes. Generalizing to "every persisted artifact more than one component reads" is what made the rule hold.

---

## See also

- [`anti-patterns.md`](anti-patterns.md) — the failure modes each principle prevents, in catalog form.
- [`../../constitution.md`](../../constitution.md) — the canonical principles.
- [`../reference/principle-fr-matrix.md`](../reference/principle-fr-matrix.md) — which FRs enforce which principle.
