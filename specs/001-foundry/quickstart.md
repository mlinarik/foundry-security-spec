# Quickstart Validation Guide: Foundry-v2

These commands describe the planned implementation. This repository currently contains specifications and planning artifacts only: package entrypoints, tests and deployment manifests below will be supplied by implementation. No live cluster, GPU or GitHub write was performed during planning.

## Prerequisites

CPython 3.12, Git, a supported container build tool, kubectl, existing Kubernetes >=1.30 with enforced Cilium and CSI RWOP, block-backed SQLite storage, TLS ingress, operator cluster identity, and authorized test fixtures. Private GPU host must serve `qwen3-coder:30b` via native Ollama HTTP. Operator supplies exact IP/CIDR+port entries, repositories/commit pins, CodeGuard corpus revision, identity groups and positive estimated token rates if yield stopping is enabled. Real GitHub/testbed credentials are Kubernetes Secrets, never committed files.

## Local structural validation (after implementation)

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes -r requirements.lock
python -m pip install --no-deps -e .
python -m pytest tests/unit tests/contract tests/integration -m 'not live_cluster and not live_model'
python -m foundry_v2.config validate --file operator-config.yaml
```

On Windows use `.venv\Scripts\Activate.ps1` and a Python 3.12 interpreter. The lockfile and package are implementation outputs. Expected: schemas and role authorization pass; all FR fixture obligations are collected; no real model or tracker is needed for deterministic structural tests. Invalid placeholder addresses, missing secrets, zero yield rates, unsafe mounts and unmatched CIDRs produce named errors before startup.

## Deployment preparation (operator-reviewed)

```sh
kubectl config current-context
kubectl kustomize deploy/overlays/operator > rendered-foundry.yaml
kubectl diff -f rendered-foundry.yaml
kubectl apply --dry-run=server -f rendered-foundry.yaml
```

Inspect namespace, external CIDRs/ports, internal selectors, RBAC, admission, RWOP storage and workload templates. Installation/apply and external publication require the user's deployment authorization at implementation time. Planning does not grant it. Supply secrets using the organization's secret management path; do not print their values or place bearer tokens in URLs. Confirm only the SQLite owner mounts its database and that replacement cannot overlap it.

## End-to-end validation (authorized test environment)

1. Run the implementation preflight command `python -m foundry_v2.cli preflight --config operator-config.yaml`. It verifies denied egress/write/API probes, operator identity, immutable source/corpus revisions, database fencing, GitHub permissions, private Ollama tool/system/token capabilities, and testbed inventory if present. Failure prevents evaluation startup.
2. Start through authenticated `POST /v1/evaluations`. Expect Indexer first, then seven other role types; pending Cartographer passes do not delay them. `GET /v1/evaluations/{id}/status` and dashboard snapshot IDs must match.
3. Use a Python/Go fixture target with known seeded security defects and clean cases. Verify rule/dependency/secret/exploratory candidates are internal until verified triage. Sample confirmed issues meet >=90% precision and include pinned citations, CWE, valid CVSS 4.0, and the fixed labels.
4. With an authorized disposable testbed, independently reproduce an exploited finding from its issue/artifact only. Without a testbed, verify no exploited flag, an unexecuted artifact and the no-testbed reason. PoC header includes Authorized testing only and setup prerequisites.
5. Kill one worker during a claim and delay a different worker's provider response while it heartbeats. Only the dead worker's claim expires within stale threshold plus one monitor cycle. Late old-generation writes return 409. Supervisor session rotation cannot revoke a healthy claim on the clock alone.
6. Race starts and claims; exactly one evaluation owns installation and no task has two holders. Crash the SQLite owner during a generation update: readers later see old or new complete state and committed progress survives replacement. Test volume/node fencing and consistent backup restore.
7. Simulate lost GitHub create response. One issue is recovered by opaque marker; uncertain create remains blocked rather than duplicating. Replay unchanged input and shift source lines: no duplicate findings/issues, only changed files parsed. Withdraw a changed nonconfirmed verdict on the original issue.
8. Lower yield with an open coverage item: fleet continues. Complete all operator goals, accumulate the positive configured spend window/minimum runtime, then lower yield: fleet drains. Unknown token accounting blocks spend-derived completion. Orchestrator keeps a monotonic local runtime watchdog so hard runtime caps remain effective during provider/substrate degradation; operator stop always works.
9. Inject provider 429/503, GitHub outage, partial map, malformed citations, prompt injection and policy failure. Check prominent degraded states, shared adaptive retry, no secret values in logs, no authority change and no automatic allowlist expansion.

## Completion evidence

Record SC-001–SC-009 results, FR fixture report, model digest/corpus revision, deployment policy probe output without credentials, sample report/PoC reproduction, stopped-evaluation ledger, and backup/restore hashes. [acceptance-coverage.md](acceptance-coverage.md) lists all 149 obligations. Live checks that cannot run are unexecuted, not passed. After tests, stop evaluation and operator-reset/delete disposable fixtures according to the inventory; retain required audit and publication provenance.
