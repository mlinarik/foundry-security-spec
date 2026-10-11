# Task generation checklist: Foundry-v2

Validated 2026-10-10. These checks assess the generated backlog; implementation and live acceptance have not run.

- [x] Loaded required spec/plan, research, data model, contracts, quickstart and unchanged constitution.
- [x] Used setup-tasks.ps1 feature directory and tasks template.
- [x] Checked extensions.yml before and after generation: no before_tasks or after_tasks hooks registered.
- [x] Organized Setup, blocking Foundation, all 14 original stories in priority order, and Polish.
- [x] Preserved original story IDs and supplied independent acceptance criteria for each story.
- [x] Generated 124 sequential unchecked tasks with explicit repository-relative file paths and correct story labels.
- [x] Restricted 10 parallel markers to independent test-authoring files after prerequisites.
- [x] Recorded explicit dependencies, fixture boundaries, per-story parallel examples and MVP strategy.
- [x] Mapped every one of 149 FR and 9 NFR to implementation and specific test/verification tasks.
- [x] Assigned all 41 OpenAPI operations to implementation tasks and a complete contract verification campaign.
- [x] Included all nine success criteria and all 11 constitution enforcement areas.
- [x] Distinguished structural fixtures from live-model precision, cluster/storage probes and human reproduction.
- [x] Ran validate-foundry-tasks.py successfully: format, story coverage, requirement references, operation ownership, dependency order and local links passed.
- [x] Preserved seed, constitution and plan; no implementation, deployment or external publication performed.

Task counts: Setup 5; Foundation 17; US1 10; US2 7; US4 6; US5 7; US6 8; US7 11; US10 8; US3 5; US8 6; US9 4; US11 5; US12 7; US13 4; US14 4; Polish 10.

The MVP is Setup + Foundation + US1 with deterministic adjacent-role fixtures. A real evaluation also requires budget and sandbox safeguards plus successful authorized preflight. Full readiness requires all story and final acceptance evidence.
