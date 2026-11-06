# Read buffer experiment — not selected

[Bext PR #422](https://github.com/benfavre/bext/pull/422) is closed without merging. Retain direct socket reads.

Five exploratory cells compare the frozen original, rebuilt direct reader, 512-byte buffer, 4096-byte buffer and frozen repeat. Screening selected 512 bytes. The independent AB/BA/AB confirmation uses 15-second loads after the original two-second warmup; screening cells are excluded from its medians.

| Arm | Median RPS | CPU ms/request | p99 ms |
| --- | ---: | ---: | ---: |
| Direct | 3,608 | 0.2772 | 31.73 |
| 512-byte buffer | 3,549 | 0.2819 | 32.43 |

Observed throughput changed **-1.64%**, and CPU cost rose **1.69%**. Paired RPS changes: -1.73%, -0.50%, +1.66%. No confidence interval or general performance guarantee is inferred from these short shared-host runs.

All 11 load/browser entries passed: **461,033 measured HTTP 200 responses**, no load errors or CPU-affinity violations, fresh render timestamps and all 24 SSR products. Counter, persisted theme and search/reset pass. All server processes and threads share CPU 10; clients exclude that physical core and sibling 22. Four V8 workers, one HTTP worker, response caching disabled, accepted preparation/hash/scanner/text/native HTML settings, warn-level tracing and retained HTTP access logging.

The canonical 18-feature PHP-ZTS build, 231 V8 tests (4 existing ignored), allocator-feature compilation, 0/512/4096 activation checks and 18 source/API freshness cases for each buffer passed. Real sockets demonstrate fewer underlying reads (4→1 for a small frame, 4→2 for a larger frame), but this did not become an observed HTTP throughput win.

Initial compile and probe-wrapper setup failures remain separate in the qualification record and sibling setup-attempt directories. They generated no valid throughput results.

[Raw comparison](comparison/analysis.json), [build, tests, source and logging provenance](qualification.json). The native prototype is unmerged; its flag is allowlisted solely for reproduction. Production is unchanged.
