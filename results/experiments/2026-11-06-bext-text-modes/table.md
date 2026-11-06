# Existing text-conversion alternatives — not selected

This screen uses the qualified merged native/SDK build: binary `2f1ce8b…`, source `a89da13e6917d3cf4c426a980295e4af7e03fd0b`, SDK `ae92033…`. It excludes the unmerged reply-transport prototype. Every server process/thread runs on CPU 10; clients exclude that core and sibling 22. Four V8 workers, one HTTP worker, 8 seconds, concurrency 50, accepted prepared/hash/scanner/native-HTML flags, detailed tracing `warn`, response cache disabled.

| Mode | Arm | RPS | CPU ms/request | p99 ms |
| --- | --- | ---: | ---: | ---: |
| 2 | control | 3,536 | 0.2849 | 30.74 |
| 3 | sized | 3,377 | 0.2995 | 32.69 |
| 4 | native-copy | 3,328 | 0.3037 | 34.73 |
| 2 | control-repeat | 3,452 | 0.2929 | 31.64 |

Mode 2 is compact conversion; 3 precomputes UTF-8 capacity; 4 copies V8 UTF-16 into request-local native memory before conversion. Both alternatives were below both control runs. Keep mode 2. This is an exploratory screen, not a paired estimate of either loss; independent confirmation and extra source-invalidation qualification were not run because neither candidate was selected.

All four cells passed browser interactions, 24-product SSR, fresh timestamps, HTTP status/error checks and CPU/thread affinity audits. There were **109,696 measured HTTP 200 responses** and zero load errors. Production was unchanged.

Raw evidence and recorded input identities: [analysis.json](analysis.json). Numeric modes 3/4 are now allowlisted by the harness for reproducibility; its default behavior is unchanged.
