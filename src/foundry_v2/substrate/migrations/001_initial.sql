CREATE TABLE installations (
 installation_id TEXT PRIMARY KEY, singleton INTEGER NOT NULL DEFAULT 1 UNIQUE CHECK(singleton=1), active_evaluation_id TEXT REFERENCES evaluations(evaluation_id),
 owner_epoch INTEGER NOT NULL DEFAULT 0, version INTEGER NOT NULL DEFAULT 0);
CREATE TABLE evaluations (
 evaluation_id TEXT PRIMARY KEY, installation_id TEXT NOT NULL REFERENCES installations(installation_id),
 state TEXT NOT NULL CHECK(state IN ('configured','preflight','indexing','running','draining','stopped','failed')),
 config_revision INTEGER NOT NULL DEFAULT 0, goals_revision INTEGER NOT NULL DEFAULT 0,
 started_at REAL, stopped_at REAL, stop_reason TEXT, degraded_json TEXT NOT NULL DEFAULT '[]',
 coverage_complete INTEGER NOT NULL DEFAULT 0 CHECK(coverage_complete IN (0,1)), version INTEGER NOT NULL DEFAULT 0);
CREATE TABLE targets (
 target_id TEXT PRIMARY KEY, vcs_url TEXT NOT NULL, repository_identity TEXT NOT NULL UNIQUE,
 pinned_commit TEXT NOT NULL, scope_json TEXT NOT NULL CHECK(json_valid(scope_json)), version INTEGER NOT NULL DEFAULT 0);
CREATE TABLE evaluation_targets (
 evaluation_id TEXT REFERENCES evaluations(evaluation_id), target_id TEXT REFERENCES targets(target_id),
 source_commit TEXT NOT NULL, index_generation TEXT REFERENCES index_generations(generation_id),
 PRIMARY KEY(evaluation_id,target_id));
CREATE TABLE config_revisions (
 revision_id TEXT PRIMARY KEY, evaluation_id TEXT NOT NULL REFERENCES evaluations(evaluation_id),
 validated_json TEXT NOT NULL CHECK(json_valid(validated_json)), author_subject TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE sessions (
 session_id TEXT PRIMARY KEY, evaluation_id TEXT NOT NULL REFERENCES evaluations(evaluation_id),
 role TEXT NOT NULL CHECK(role IN ('orchestrator','indexer','cartographer','detector','triager','validator','reporter','coverage-guide')),
 slot INTEGER NOT NULL CHECK(slot>=0), incarnation INTEGER NOT NULL CHECK(incarnation>=0),
 pod_name TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('registered','running','draining','stopped','dead')),
 heartbeat_at REAL, restart_count INTEGER NOT NULL DEFAULT 0, version INTEGER NOT NULL DEFAULT 0);
CREATE UNIQUE INDEX live_role_slot ON sessions(evaluation_id,role,slot) WHERE state IN ('registered','running','draining');
CREATE TABLE tasks (
 task_id TEXT PRIMARY KEY, evaluation_id TEXT NOT NULL REFERENCES evaluations(evaluation_id),
 target_id TEXT REFERENCES targets(target_id), queue_name TEXT NOT NULL DEFAULT 'work', role TEXT NOT NULL,
 title TEXT NOT NULL, description TEXT NOT NULL, priority INTEGER NOT NULL CHECK(priority>=0),
 state TEXT NOT NULL DEFAULT 'open' CHECK(state IN ('open','blocked','closed')),
 release_count INTEGER NOT NULL DEFAULT 0, version INTEGER NOT NULL DEFAULT 0);
CREATE INDEX task_order ON tasks(evaluation_id,queue_name,state,priority,task_id);
CREATE TABLE claims (
 resource_type TEXT NOT NULL CHECK(resource_type IN ('task','finding','file')), resource_id TEXT NOT NULL,
 evaluation_id TEXT NOT NULL REFERENCES evaluations(evaluation_id), holder_session_id TEXT REFERENCES sessions(session_id),
 generation INTEGER NOT NULL CHECK(generation>=0), acquired_at REAL, PRIMARY KEY(resource_type,resource_id));
CREATE TABLE findings (
 finding_id TEXT PRIMARY KEY, target_id TEXT NOT NULL REFERENCES targets(target_id), fingerprint TEXT NOT NULL,
 path TEXT NOT NULL, symbol TEXT NOT NULL, weakness_key TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 0,
 UNIQUE(target_id,fingerprint));
CREATE TABLE finding_observations (
 observation_id TEXT PRIMARY KEY, evaluation_id TEXT NOT NULL REFERENCES evaluations(evaluation_id),
 finding_id TEXT NOT NULL REFERENCES findings(finding_id), candidate_technique TEXT NOT NULL,
 corpus_revision TEXT, verdict TEXT CHECK(verdict IN ('true-positive','false-positive','needs-review','not-applicable','code-quality')),
 evidence_id TEXT REFERENCES evidence(evidence_id), validation_id TEXT REFERENCES validation_attempts(attempt_id),
 report_revision TEXT REFERENCES reports(report_revision), exploited INTEGER NOT NULL DEFAULT 0 CHECK(exploited IN (0,1)),
 version INTEGER NOT NULL DEFAULT 0, UNIQUE(evaluation_id,finding_id));
CREATE TABLE blobs (
 digest TEXT PRIMARY KEY CHECK(length(digest)=64), byte_length INTEGER NOT NULL CHECK(byte_length>=0),
 media_type TEXT NOT NULL, committed_at REAL NOT NULL, ref_count INTEGER NOT NULL DEFAULT 0 CHECK(ref_count>=0));
CREATE TABLE evidence (
 evidence_id TEXT PRIMARY KEY, observation_id TEXT NOT NULL REFERENCES finding_observations(observation_id),
 entry_citations TEXT NOT NULL, trust_citations TEXT NOT NULL, impact_citations TEXT NOT NULL,
 citation_check TEXT NOT NULL, presence_carveout TEXT, reasoning_blob TEXT NOT NULL REFERENCES blobs(digest));
CREATE TABLE validation_attempts (
 attempt_id TEXT PRIMARY KEY, observation_id TEXT NOT NULL REFERENCES finding_observations(observation_id),
 author_session_id TEXT NOT NULL REFERENCES sessions(session_id), reproduction_session_id TEXT REFERENCES sessions(session_id),
 artifact_digest TEXT REFERENCES blobs(digest), result TEXT NOT NULL CHECK(result IN ('success','failed','partial','no_testbed','prohibited')),
 observed_impact TEXT, explanation TEXT NOT NULL, CHECK(result<>'success' OR
 (reproduction_session_id IS NOT NULL AND author_session_id<>reproduction_session_id AND observed_impact IS NOT NULL AND length(observed_impact)>0)));
CREATE TABLE reports (
 report_revision TEXT PRIMARY KEY, observation_id TEXT NOT NULL REFERENCES finding_observations(observation_id),
 markdown_digest TEXT NOT NULL REFERENCES blobs(digest), cwe_id TEXT NOT NULL, cvss_vector TEXT NOT NULL,
 cvss_score REAL NOT NULL CHECK(cvss_score BETWEEN 0 AND 10), tier TEXT NOT NULL,
 version INTEGER NOT NULL DEFAULT 0);
CREATE TABLE publications (
 publication_id TEXT PRIMARY KEY, target_id TEXT NOT NULL REFERENCES targets(target_id), fingerprint TEXT NOT NULL,
 desired_report_revision TEXT REFERENCES reports(report_revision), state TEXT NOT NULL
 CHECK(state IN ('pending','creating','uncertain','published','updating','withdrawn','blocked')),
 repo TEXT NOT NULL, issue_number INTEGER, marker TEXT NOT NULL UNIQUE, version INTEGER NOT NULL DEFAULT 0,
 UNIQUE(target_id,fingerprint));
CREATE TABLE outbox (
 command_id TEXT PRIMARY KEY, evaluation_id TEXT NOT NULL REFERENCES evaluations(evaluation_id),
 kind TEXT NOT NULL, payload TEXT NOT NULL CHECK(json_valid(payload)), state TEXT NOT NULL, last_error TEXT,
 version INTEGER NOT NULL DEFAULT 0);
CREATE TABLE index_generations (
 generation_id TEXT PRIMARY KEY, evaluation_id TEXT NOT NULL REFERENCES evaluations(evaluation_id),
 target_id TEXT NOT NULL REFERENCES targets(target_id), source_commit TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('building','ready','failed')), parent_generation TEXT REFERENCES index_generations(generation_id));
CREATE TABLE code_units (
 unit_id TEXT NOT NULL, generation_id TEXT NOT NULL REFERENCES index_generations(generation_id),
 path TEXT NOT NULL, symbol TEXT NOT NULL, language TEXT NOT NULL, ranges TEXT NOT NULL,
 body_digest TEXT NOT NULL REFERENCES blobs(digest), file_hash TEXT NOT NULL,
 PRIMARY KEY(generation_id,unit_id), UNIQUE(generation_id,path,symbol));
CREATE TABLE call_edges (
 generation_id TEXT NOT NULL REFERENCES index_generations(generation_id), caller_id TEXT NOT NULL,
 callee_id TEXT, unresolved_name TEXT, kind TEXT NOT NULL CHECK(kind IN ('static','resolved_indirect','unresolved')),
 FOREIGN KEY(generation_id,caller_id) REFERENCES code_units(generation_id,unit_id),
 FOREIGN KEY(generation_id,callee_id) REFERENCES code_units(generation_id,unit_id));
CREATE TABLE security_documents (
 doc_id TEXT PRIMARY KEY, evaluation_id TEXT NOT NULL REFERENCES evaluations(evaluation_id), kind TEXT NOT NULL,
 generation INTEGER NOT NULL, content_digest TEXT NOT NULL REFERENCES blobs(digest), fallback INTEGER NOT NULL,
 source_revision TEXT NOT NULL, UNIQUE(evaluation_id,kind,generation));
CREATE TABLE coverage_items (
 item_id TEXT PRIMARY KEY, evaluation_id TEXT NOT NULL REFERENCES evaluations(evaluation_id), goals_revision INTEGER NOT NULL,
 component TEXT NOT NULL, goal TEXT NOT NULL, attempt_bar TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('open','closed')),
 evidence_refs TEXT NOT NULL DEFAULT '[]', version INTEGER NOT NULL DEFAULT 0, UNIQUE(evaluation_id,goals_revision,component,goal));
CREATE TABLE coverage_attempts (
 attempt_id TEXT PRIMARY KEY, item_id TEXT REFERENCES coverage_items(item_id), evaluation_id TEXT NOT NULL REFERENCES evaluations(evaluation_id),
 session_id TEXT NOT NULL REFERENCES sessions(session_id), area TEXT NOT NULL, technique TEXT NOT NULL,
 result TEXT NOT NULL, evidence_refs TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE model_calls (
 call_id TEXT PRIMARY KEY, evaluation_id TEXT NOT NULL REFERENCES evaluations(evaluation_id), session_id TEXT NOT NULL REFERENCES sessions(session_id),
 model_tag TEXT NOT NULL, digest TEXT, state TEXT NOT NULL CHECK(state IN ('reserved','completed','interrupted')),
 prompt_tokens INTEGER CHECK(prompt_tokens>=0), output_tokens INTEGER CHECK(output_tokens>=0), rates TEXT,
 amount TEXT, usage_status TEXT NOT NULL CHECK(usage_status IN ('known','estimated','unknown')), version INTEGER NOT NULL DEFAULT 0);
CREATE TABLE provider_state (
 provider_id TEXT PRIMARY KEY, blocked_until REAL, reason TEXT, retry_observations TEXT NOT NULL DEFAULT '[]', version INTEGER NOT NULL DEFAULT 0);
CREATE TABLE operator_messages (
 message_id TEXT PRIMARY KEY, evaluation_id TEXT NOT NULL REFERENCES evaluations(evaluation_id), session_id TEXT NOT NULL REFERENCES sessions(session_id),
 kind TEXT NOT NULL CHECK(kind IN ('blocker','request','feedback','info')), dedup_key TEXT NOT NULL, body TEXT NOT NULL,
 created_at REAL NOT NULL, acknowledged_at REAL, version INTEGER NOT NULL DEFAULT 0);
CREATE TABLE checkpoint_tuples (
 evaluation_id TEXT NOT NULL REFERENCES evaluations(evaluation_id), thread_id TEXT NOT NULL, namespace TEXT NOT NULL,
 checkpoint_id TEXT NOT NULL, parent_id TEXT, metadata TEXT NOT NULL,
 channels_digest TEXT NOT NULL REFERENCES blobs(digest), version_map TEXT NOT NULL, codec_version TEXT NOT NULL,
 PRIMARY KEY(evaluation_id,thread_id,namespace,checkpoint_id));
CREATE TABLE checkpoint_writes (
 evaluation_id TEXT NOT NULL, thread_id TEXT NOT NULL, namespace TEXT NOT NULL, checkpoint_id TEXT NOT NULL,
 task_id TEXT NOT NULL, write_index INTEGER NOT NULL, task_path TEXT NOT NULL, channel TEXT NOT NULL,
 value_digest TEXT NOT NULL REFERENCES blobs(digest), PRIMARY KEY(evaluation_id,thread_id,namespace,checkpoint_id,task_id,write_index),
 FOREIGN KEY(evaluation_id,thread_id,namespace,checkpoint_id) REFERENCES checkpoint_tuples(evaluation_id,thread_id,namespace,checkpoint_id));
CREATE TABLE audit_events (
 sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE, evaluation_id TEXT REFERENCES evaluations(evaluation_id),
 actor_kind TEXT NOT NULL, actor_id TEXT NOT NULL, action TEXT NOT NULL, resource TEXT NOT NULL,
 prior_version INTEGER, new_version INTEGER, reason TEXT, created_at REAL NOT NULL);
CREATE TABLE idempotency_keys (
 actor_id TEXT NOT NULL, method TEXT NOT NULL, path TEXT NOT NULL, key TEXT NOT NULL,
 request_digest TEXT NOT NULL, response_json TEXT NOT NULL CHECK(json_valid(response_json)), response_status INTEGER NOT NULL,
 PRIMARY KEY(actor_id,method,path,key));
CREATE TABLE credentials (
 credential_id TEXT PRIMARY KEY, evaluation_id TEXT NOT NULL REFERENCES evaluations(evaluation_id),
 session_id TEXT REFERENCES sessions(session_id), role TEXT NOT NULL, token_hash TEXT NOT NULL UNIQUE CHECK(length(token_hash)=64),
 expires_at REAL NOT NULL, revoked_at REAL);
