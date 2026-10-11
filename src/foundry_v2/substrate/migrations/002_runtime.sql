CREATE TABLE blob_grants (
 evaluation_id TEXT NOT NULL REFERENCES evaluations(evaluation_id), digest TEXT NOT NULL REFERENCES blobs(digest),
 grantee TEXT NOT NULL, purpose TEXT NOT NULL CHECK(purpose IN ('artifact','checkpoint')),
 PRIMARY KEY(evaluation_id,digest,grantee,purpose));
CREATE TABLE checkpoint_threads (
 evaluation_id TEXT NOT NULL REFERENCES evaluations(evaluation_id), thread_id TEXT NOT NULL,
 session_id TEXT NOT NULL REFERENCES sessions(session_id), PRIMARY KEY(evaluation_id,thread_id));
CREATE TABLE checkpoint_pending (
 evaluation_id TEXT NOT NULL REFERENCES evaluations(evaluation_id), thread_id TEXT NOT NULL, namespace TEXT NOT NULL,
 checkpoint_id TEXT NOT NULL, task_id TEXT NOT NULL, write_index INTEGER NOT NULL, task_path TEXT NOT NULL,
 channel TEXT NOT NULL, value_digest TEXT NOT NULL REFERENCES blobs(digest),
 PRIMARY KEY(evaluation_id,thread_id,namespace,checkpoint_id,task_id,write_index));
CREATE TABLE transcript_chunks (
 sequence INTEGER PRIMARY KEY AUTOINCREMENT, evaluation_id TEXT NOT NULL REFERENCES evaluations(evaluation_id),
 session_id TEXT NOT NULL REFERENCES sessions(session_id), kind TEXT NOT NULL,
 content_digest TEXT NOT NULL REFERENCES blobs(digest), created_at REAL NOT NULL);
CREATE TABLE runtime_records (
 evaluation_id TEXT NOT NULL REFERENCES evaluations(evaluation_id), kind TEXT NOT NULL, resource_id TEXT NOT NULL,
 payload TEXT NOT NULL CHECK(json_valid(payload)), version INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(evaluation_id,kind,resource_id));
