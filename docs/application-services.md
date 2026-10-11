# Foundation application services

The Orchestrator and substrate are runnable HTTP/HTTPS services. They implement installation inspection, persisted evaluation snapshots, infrastructure-only session registration/credential provisioning, worker heartbeats and task queue/claim operations. SQLite is accessed only by the substrate. The Orchestrator serves a small dashboard, validates operator TokenReview identities and forwards the same operator bearer to the substrate for a second authorization check.

Evaluation start returns `503 evaluation_runtime_incomplete`. Worker graphs, checkpoints, source/model integrations, reporting, budget governance and production sandbox acceptance are still unfinished. The remaining tasks stay open; these services do not constitute a complete autonomous security evaluation system. There is no anonymous control access, synthetic evaluation, zero-spend assumption or alternate database/storage fallback.

## Deployment inputs

Use `deploy/services/operator-inputs.example.json` as the input shape. Its placeholder storage class and empty operator allowlists deliberately fail validation. Supply an actual CSI block-backed storage class supporting RWOP and at least one authorized Kubernetes username/group. `storage_size`, stale/reaper intervals and release limit are explicit operator tunables; the example values are illustrative. The namespace is dedicated to these services. No ingress or workers are created by this increment; cluster-internal access is available through the two Services.

The default profile uses CSI RWOP and TLS. On 2026-10-11 the operator explicitly requested existing cluster-local storage and no TLS certificate. `deploy/services/cluster-inputs.json` records that runtime override: private HTTP on port 8080, a dedicated Retain local PV on k8s0n1 using `/data/foundry-v2`, RWO, Recreate updates and lifetime SQLite owner locking. It creates a dedicated `operator` service account allowed only at the application boundary; that account receives no Kubernetes management roles. This deployment does not claim CSI RWOP/node-failover fencing or TLS protection. The canonical spec and default profile remain unchanged.

The local directory is initialized by a temporary maintenance Job in its own namespace, with only the dedicated directory mounted, no API token, read-only root and only CHOWN capability. The initializer refuses a nonempty directory, requires at least 10Gi of free space and sets owner 10001/mode 0700. Its namespace is removed after initialization. The local PV capacity declaration does not impose a filesystem quota; data remains on the selected node and no automatic cross-node failover is offered.

Secrets, in the selected namespace:

- `foundry-service-tls` (HTTPS profile only): `tls.crt`, `tls.key`, `ca.crt`. The certificate must cover `substrate.<namespace>.svc` and any service/client DNS names used. The Orchestrator verifies the substrate against `ca.crt`. Kubernetes CA trust is separate.
- `foundry-infrastructure`: `token`, a cryptographically random dedicated token of at least 32 characters; only the substrate mounts it at this stage. It authenticates infrastructure registration/provisioning and cannot authenticate as an operator. Never copy it into model tools.
- `harbor-pull-secret`: a `kubernetes.io/dockerconfigjson` Secret scoped to the published Harbor repository.

Keep Secret values outside Git. Both service accounts have only `create tokenreviews`; their projected API tokens are mounted explicitly and automount is disabled. Neither service can create Jobs, edit policies, grant RBAC or mount host files. Future lifecycle authority requires the remaining planned controller/admission work.

```powershell
python deploy/services/render.py --image <immutable-Harbor-reference> --config <operator-inputs.json> > <rendered-services.yaml>
# Review namespace/policies first; provision required Secrets through your secret management path.
python deploy/services/preflight.py --image <immutable-Harbor-reference> --config <operator-inputs.json>
kubectl apply --dry-run=server -f <rendered-services.yaml>
kubectl apply -f <rendered-services.yaml>
kubectl rollout status deployment/substrate -n foundry-v2 --timeout=60s
kubectl rollout status deployment/orchestrator -n foundry-v2 --timeout=60s
```

Preflight is read-only and checks current cluster/storage/Secret inputs. It does not establish node fencing, effective network isolation or model quality. Those are separate acceptance gates and evaluation start remains disabled. SMB, NFS and emptyDir remain unsupported database storage. The explicit local-rwo override is accepted only for the dedicated static local PV; it is never an automatic fallback.

## API and access

`GET /healthz` reports process liveness; `GET /readyz` checks owner/reaper health or substrate TLS connectivity. Authenticated routes require HTTPS by default; the explicit private-HTTP deployment override retains all bearer identity checks. `GET /v1/installation` reports the active evaluation and start blockers; `GET /v1/evaluations/{id}/status` projects the same owner snapshot as `/substrate/v1/evaluations/{id}/snapshot`. No evaluation is created merely by deploying the services.

Operator tokens must be issued for the configured `foundry-v2` audience and validate through Kubernetes TokenReview; the returned username/group must match the explicit allowlist. The browser retains the bearer only in memory and uses text rendering for returned state. Use an organization-approved token issuance path. Never place a token in a URL, shared command history or committed file.

Infrastructure-only extensions to the canonical API are `POST /substrate/v1/evaluations/{id}/credentials` (`session_id`, `role`, `token`, `expires_at`) and `DELETE /substrate/v1/evaluations/{id}/sessions/{session_id}/credentials`. Only credential hashes are stored. All mutations require an Idempotency-Key; raw token values are excluded from receipt hashes and responses. Full canonical OpenAPI reconciliation remains task T120.

Task claims currently cover task resources. Finding/file claims, blob scope grants, checkpoint transport and complete generation writes remain open foundation obligations. Unsupported operations fail closed rather than accepting arbitrary payload writes. Heartbeats use server receipt time and idempotent replay cannot refresh liveness; the reaper releases stale claims and revokes dead session credentials. Repeated task releases reach the configured blocked state. Reprioritization changes order without changing task IDs.

Access the deployed private HTTP service through a local-only tunnel:

```powershell
kubectl port-forward -n foundry-v2 service/orchestrator 8080:8080 --address 127.0.0.1
# In another terminal, mint an audience-scoped short-lived operator token using your authorized cluster identity:
kubectl create token operator -n foundry-v2 --audience=foundry-v2 --duration=15m
```

Open http://127.0.0.1:8080 and paste the token into the dashboard. The token is not saved to disk or browser storage. No public ingress, DNS record or model workload is installed.

Deployment evidence: `deploy/services/live-results.json` records service readiness, TokenReview positive/negative checks, restart persistence, owner lock and read-only mount checks. All 53 structural tests passed both in the restricted local Linux container and in the isolated Kubernetes validation Job; its output is `deploy/services/kubernetes-test-results.txt`. The two running services use the immutable image recorded in `deploy/images/published-services.json`.
