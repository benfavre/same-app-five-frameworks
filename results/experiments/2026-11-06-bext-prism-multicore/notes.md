# PRISM with the full machine available, 2026-11-06

The Ryzen 9 5900X host has 12 physical cores and 24 logical CPUs. All server processes, V8 subprocesses and helper threads may use CPUs 0–23. The load generator and Chrome run on the same machine with the same mask; CPU availability is shared with other services. These are configured-instance results, separate from the one-CPU comparison. They do not establish a hardware throughput ceiling.

| V8 / HTTP workers | Connections | RPS median | RPS min–max | Server CPU equivalents | CPU ms/request | p99 |
|---|---:|---:|---:|---:|---:|---:|
| 4 / 1 | 50 | 10,969 | 10,928–11,122 | 2.77 | 0.2684 | 7.15 ms |
| 12 / 12 | 50 | 36,118 | 35,538–37,254 | 14.02 | 0.4128 | 3.23 ms |
| 16 / 24 | 50 | 34,734 | 34,217–38,144 | 14.59 | 0.4436 | 3.56 ms |

Each row contains three fresh-server runs with 20 seconds of warmup followed by 15 seconds at 50 connections. The worker profiles rotate in ABC/BCA/CAB order. Ranges are observed variation on a shared host, not confidence intervals.

The accepted native binary and frozen SDK are unchanged. Prepared page setup, legacy hash hints, token scanning, compact text mode 2 and native HTML scanning are enabled; multiplexing is off. Default nursery and IPC remain selected. Render-result caching is disabled, and the fixture renders dynamically. Continuous profiling and HTTP access logs remain enabled with detailed Rust tracing at warn. Worker overrides apply only to these private benchmark servers.

All **9 completed load/browser entries** passed: **3,736,457 measured HTTP 200 responses**, zero load errors and zero CPU-affinity violations. Each entry checks 24 raw SSR products, fresh idle/load timestamps, counter, persisted theme and search/reset. CPU equivalents sum CPU time across the controller and every child process and divide by the audit interval; these are logical-CPU equivalents, not physical-core counts. CPU/request uses the measured response count. Client CPU time is excluded from the server figure.

**The heavier-load check failed.** At 200 connections with 16 V8 / 24 HTTP workers, the 20-second warmup returned 737,208 HTTP 200 and 150,977 HTTP 503 responses (about 17% rejected). The measured load then failed its freshness request with another 503 and was aborted. Its empty load output and missing browser/freshness results are retained; no RPS result from that attempt qualifies for this table. A transport-level oha success rate of 1.0 does not make non-200 responses pass the contract. The two remaining planned sweeps did not run.

The initial heavier-load wrapper omitted its pinned runtime environment and failed before starting any server/load. That failed setup is retained in [a separate directory](../2026-11-06-bext-prism-multicore-initial-saturation-setup/). The corrected attempt uses the same binary/SDK as all nine 50-connection cells. No memory/disk/deadline limit was breached; the overload failure is separate from resource guarding. Production was unchanged.

[Raw worker comparison](analysis.json), [failed heavier-load campaign](saturation-200/campaign.json), [qualification and local access-log retention](qualification.json). The one-CPU benchmark pointers remain unchanged.

## Reproduce

Set `BEXT_BIN` and `BEXT_SHARED_FRAMEWORK_DIR` to the qualified merged runtime and SDK. Choose CPU IDs available on your machine. Serialize heavy work with the same lock used by other local benchmarks (activ-2 uses `~/.local/state/bext-prism-scaling-20261031/measurement.lock`).

```bash
python3 harness/compare-bext-multicore.py \
  --binary "$BEXT_BIN" --framework "$BEXT_SHARED_FRAMEWORK_DIR" \
  --server-cpus 0-23 --client-cpus 0-23 \
  --lock-file /tmp/same-app-five-frameworks.lock \
  --output results/experiments/local-multicore

# The separate 200-connection workload uses the same accepted flags:
npm run benchmark -- --frameworks bext --repeats 3 --cold-samples 1 \
  --warmup-seconds 20 --duration 15 --concurrency 200 \
  --server-cpus 0-23 --client-cpus 0-23 \
  --bext-v8-workers 16 --bext-http-workers 24 --bext-log-filter warn \
  --bext-flag BEXT_PRISM_PREPARED_PAGES=1 --bext-flag BEXT_V8_LEGACY_HASH_HINT=1 \
  --bext-flag BEXT_V8_MULTIPLEX=0 --bext-flag BEXT_PRISM_TOKEN_SCAN=1 \
  --bext-flag BEXT_V8_PREPARED_TEXT=2 --bext-flag BEXT_PRISM_NATIVE_HTML_SCAN=1 \
  --output results/experiments/local-multicore-200
```
