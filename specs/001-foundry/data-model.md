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
