# Reconciled native and SDK validation

The native/SDK recovery and legacy bundle hash reuse are merged in [Bext PR #419](https://github.com/benfavre/bext/pull/419) and [PR #420](https://github.com/benfavre/bext/pull/420). This validation uses their combined source at `a89da13e6917d3cf4c426a980295e4af7e03fd0b`; merged `master` at `e64d643d7a8ae43fac1fa3af4f4366bddfdb244d` has identical native and SDK build inputs.

| Check | Result |
| --- | --- |
| Canonical 18-feature PHP-ZTS release build | Pass |
| Default V8 release tests | 228 passed, 4 existing ignored |
| Cells-enabled V8 release tests | 231 passed, 4 existing ignored |
| WordPress/nginx/H3 regression tests | 15 passed |
| Full server plus Cells compilation | Pass |
| SDK scanner, response and metadata tests | 34 passed, 351 assertions |
| Page/layout/import/API invalidation and request freshness | 18 cases passed |

All measurements pin every server process and thread to CPU 10 and exclude that core and its SMT sibling from clients. Four V8 workers, one HTTP worker, response caching disabled, prepared pages/hash reuse/scanner/text/native HTML flags enabled, detailed Rust tracing set to `warn`; HTTP access logging remains enabled. Shared-host sweeps are 8 seconds at concurrency 50.

| Run | RPS | CPU ms/request | p99 ms |
| --- | ---: | ---: | ---: |
| 1 | 3,415 | 0.2950 | 30.85 |
| 2 | 2,939 | 0.3430 | 42.50 |
| 3 | 3,490 | 0.2901 | 30.21 |
| Median | 3,415 | 0.2950 | 30.85 |

The slower second run is retained. These are compatibility checks on the coherent native/SDK source, not a paired speedup claim or a replacement for the [five-framework candidate sweep](../2026-11-05-five-frameworks-bext-candidate/table.md). Native binary SHA-256: `2f1ce8b160f416b5cbba862503e5939be285d391195ce5091aa11d94e6d1f1ac`; SDK manifest SHA-256: `ae92033bc02dc15d6586a2f88b81092b3829ccc8e3478ea2e03ad4a0e130762e`.

Raw evidence: [qualification.json](qualification.json), [candidate campaign](candidate/). Source and external dependency fingerprints stayed unchanged. The build stayed below its 10 GiB RSS cap with at least 8 GiB host memory available. Production was unchanged.
