# Direct props serializer experiment — not selected

[Bext PR #424](https://github.com/benfavre/bext/pull/424) is closed without merging. Retain the existing materialized props path.

Three balanced ABC/BCA/CAB blocks compare the frozen original, rebuilt off and rebuilt on. Every cell uses 20 seconds of warmup and 15 seconds of load. Both rebuilt arms use the same artifact.

| Arm | Median RPS | CPU ms/request | p99 ms |
| --- | ---: | ---: | ---: |
| Frozen original | 3,964 | 0.2525 | 28.55 |
| Rebuilt off | 3,922 | 0.2544 | 28.52 |
| Rebuilt on | 3,898 | 0.2566 | 30.23 |

Observed throughput changed **-0.62%**, and CPU cost rose **0.85%**. Paired RPS changes: -5.69%, -1.41%, -0.62%. No confidence interval or general performance guarantee is inferred from these short shared-host runs.

All 9 load/browser entries passed: **527,105 measured HTTP 200 responses**, no load errors or CPU-affinity violations, fresh render timestamps and all 24 SSR products. Counter, persisted theme and search/reset pass. All server processes and threads share CPU 10; clients exclude that physical core and sibling 22. Four V8 workers, one HTTP worker, response caching disabled, accepted preparation/hash/scanner/text/native HTML settings, warn-level tracing and retained HTTP access logging.

Two focused wire tests pass in each serde_json map configuration. The corrected canonical 18-feature PHP-ZTS build passes. All 36 HTTP props cases match the original behavior: 33 HTTP 200 responses and three matching existing malformed-query 500 responses. The checker compares HTTP-visible semantic fields because HashMap parameter order already varies; raw field ordering is independently checked in both serde map configurations. Eighteen source/layout/import/API freshness cases pass with the direct serializer enabled.

The first prototype and its failed strict-conformance attempts are retained separately, including the intermediate artifact and source manifests. The final serializer preserves map configuration and parameter representation. These correctness passes do not erase the failed performance result.

[Raw comparison](comparison/analysis.json), [build, tests, source and logging provenance](qualification.json). The native prototype is unmerged; its flag is allowlisted solely for reproduction. Production is unchanged.
