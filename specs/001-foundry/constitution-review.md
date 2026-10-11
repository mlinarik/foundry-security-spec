# Constitution Review: Foundry-v2

Date: 2026-10-10. Authority: `.specify/memory/constitution.md` v0.2.0, unchanged. Original constitution requirement references are interpreted through `requirement-id-map.md`. This is a specification conformance review, not proof of implementation compliance.

| Principle | DRAFT enforcing requirements | Review |
|---|---|---|
| I. Evidence Over Assertion | FR-053, FR-054, FR-089, FR-091 | Covered; acceptance obligations in acceptance-coverage.md |
| II. Surface Only What Survives | FR-046, FR-059, FR-081 | Covered; acceptance obligations in acceptance-coverage.md |
| III. Liveness By Heartbeat | FR-006, FR-099, FR-104, FR-129 | Covered; acceptance obligations in acceptance-coverage.md |
| IV. Atomic Mortal Claims | FR-098, FR-099 | Covered; acceptance obligations in acceptance-coverage.md |
| V. Provider Rate Arbiter | FR-115, FR-116 | Covered; acceptance obligations in acceptance-coverage.md |
| VI. Coverage Before Yield | FR-073, FR-126, FR-127 | Covered; acceptance obligations in acceptance-coverage.md |
| VII. Exploited Means Demonstrated | FR-062, FR-063, FR-092 | Covered; acceptance obligations in acceptance-coverage.md |
| VIII. Stable Fingerprints | FR-047, FR-093, FR-094 | Covered; acceptance obligations in acceptance-coverage.md |
| IX. Infrastructure Sandbox | FR-118, FR-119, FR-135 | Covered; acceptance obligations in acceptance-coverage.md |
| X. Operator Authority | FR-019, FR-070, FR-106, FR-114 | Covered; acceptance obligations in acceptance-coverage.md |
| XI. Atomic Persistence | FR-026, FR-076, FR-117, FR-138 | Covered; acceptance obligations in acceptance-coverage.md |

Operator runtime overrides remain recorded exceptions; automated behavior never gains override authority. Session rotation terminates a session without clock-based claim reclamation; remaining claims expire only by heartbeat. Role counts express operator fleet composition, not a guessed provider-rate ceiling. Kubernetes namespace placement does not constitute isolation; enforced controls and preflight are required. SQLite owner and publication recovery must preserve atomicity. Local estimated monetary rates remain operator configuration and cannot be fabricated.
