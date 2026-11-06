# Merged-source tuned comparison, 2026-11-06

This campaign uses the accepted Bext configuration from public merged master, not the rejected transport prototype. The qualified binary is `2f1ce8b160f416b5cbba862503e5939be285d391195ce5091aa11d94e6d1f1ac`; SDK manifest is `ae92033bc02dc15d6586a2f88b81092b3829ccc8e3478ea2e03ad4a0e130762e`. Source `a89da13e6917d3cf4c426a980295e4af7e03fd0b` has identical native/SDK inputs to merged master `e64d643d7a8ae43fac1fa3af4f4366bddfdb244d`.

Bext settings are recorded in [qualification.json](qualification.json): prepared pages/hash reuse/scanner/native HTML enabled, compact text mode 2, multiplex 0, four V8 workers, one HTTP worker, default nursery/response transport, detailed Rust tracing `warn`, HTTP access logging enabled. Response caching is disabled. The other frameworks retain their normal production start commands.

All 15 browser/load entries pass; 211,132 measured responses were HTTP 200, with zero load errors or CPU/thread-affinity violations. All server threads/processes share CPU 10; clients exclude CPUs 10 and 22. Process starts are warm-filesystem measurements: three samples per entry per sweep. Production is unchanged.

The machine is shared and the CPU is not exclusively reserved. The three ranges show observed variation; no confidence interval or general p99 guarantee is inferred. The separate default-settings baseline remains archived; this tuned campaign does not overwrite `results/latest.json`.

[Full table](table.md), [summary](summary.json), [metadata](metadata.json), [native/SDK validation](../2026-11-05-bext-reconciled/table.md).
