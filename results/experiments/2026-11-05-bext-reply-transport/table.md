# Reply transport experiment — not selected

[Bext PR #421](https://github.com/benfavre/bext/pull/421) is closed without merging. Independent confirmation regressed throughput and CPU cost, so the existing copied writer remains selected.

All server processes and threads run on CPU 10; clients exclude CPU 10 and SMT sibling 22. Four V8 workers, one HTTP worker, caching disabled, prepared pages/hash reuse/scanner/text/native HTML enabled, Rust tracing `warn`, HTTP access logging enabled. All timed cells use 8 seconds at concurrency 50 and the same SDK manifest (`ae92033…`).

## Exploratory screen

The previous qualified binary is `2f1ce8b…`; the prototype is `f2cffc71…` from native source `d7841975516c8d96cd7f261b4c470a4909bca9ea`. Their copied-writer screen cells check rebuild drift. The screen selects a candidate for fresh confirmation; it does not establish a gain.

| Arm | RPS | CPU ms/request | p99 ms |
| --- | ---: | ---: | ---: |
| original | 3,435 | 0.2940 | 30.67 |
| copied | 3,436 | 0.2952 | 31.32 |
| vectored | 3,376 | 0.2982 | 33.00 |
| shared-memory | 3,564 | 0.2839 | 30.16 |
| original-repeat | 3,298 | 0.3058 | 32.68 |

## Independent confirmation

AB/BA/AB compares copied and shared-memory writers in the same prototype binary. Screening cells are excluded.

| Arm | Median RPS | CPU ms/request | p99 ms |
| --- | ---: | ---: | ---: |
| control | 3,498 | 0.2886 | 30.03 |
| candidate | 3,422 | 0.2954 | 33.83 |

Throughput changed **-2.16%**, and CPU cost rose **2.38%**. Paired RPS changes were +4.25%, -2.16%, -5.69%. These are short shared-host observations, not confidence intervals. The first screening cell for shared memory was promising; two of three independent pairs lost.

## Correctness and retention

The canonical 18-feature PHP-ZTS build and 231 V8 tests pass (4 existing ignored). All 11 cells pass browser interactions, 24-product SSR, fresh render timestamps, CPU/thread affinity and HTTP error checks: **303,167 measured HTTP 200 responses, zero errors**. Each alternative passes 18 source/layout/import/API freshness cases, including fresh GET/POST request data. Access-log counts cover at least all measured responses. No production change was made.

Owned-process activation probes show four worker regions in every mode; the controller maps all four only in shared-memory mode. Socket tests cover exact inline bytes, UTF-8/NUL, empty/errors, exact slot capacity, oversize responses, busy-slot fallback and slot reuse.

Raw evidence: [comparison](comparison/analysis.json), [build/check/logging provenance](qualification.json), [activation 0](activation-0/proof.json), [activation 1](activation-1/proof.json), [activation 2](activation-2/proof.json), [freshness 1](source-freshness-1.json), [freshness 2](source-freshness-2.json). The failed performance result is retained separately from correctness passes.

A [diagnostic profile](profiles/flat-report.txt) of the optimized copied-writer control uses the prototype with transport mode 0, not a throughput comparison. Its known-symbol self samples show smaller former ICU/string-conversion hotspots and distributed allocation/kernel/filesystem work. The [inclusive report](profiles/inclusive-report.txt) contains substantial incomplete/unresolved stacks; its sentinel is not an attributable function. Raw perf data remains local with its hash and path in [retention metadata](profiles/retention.json).

Reproduce with `harness/compare-bext-reply-transports.py --original <qualified-binary> --candidate <prototype> --framework <same-sdk> --output <new-directory>`; use the CPU masks and lock options documented by the runner. `harness/check-bext-reply-transport.py --mode 0|1|2 --output <new-directory>` verifies activation using `BEXT_BIN` and `BEXT_SHARED_FRAMEWORK_DIR`. The new flag is available only in the unmerged prototype.
