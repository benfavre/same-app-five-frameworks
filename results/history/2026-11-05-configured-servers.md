# Same app, five frameworks — unrestricted configured servers, 2026-11-05

Production SSR measurement on activ-2, 19:51:59–19:56:35 UTC. Three equal sweeps
per framework; medians below retain every attempt. Every entry passed the uncached
idle/load proof, all 24 SSR product checks, and counter/theme/search checks in a
real browser, including theme persistence and search reset.

| Framework | Client JS (KiB gz) | TTFB p50 (ms) | RPS median | RPS min–max | p99 (ms) | Process start (ms) | Output (KiB) | C/T/S |
|---|---:|---:|---:|---:|---:|---:|---:|:---:|
| bext (PRISM) | 5.71 | 3.10 | 15,874 | 15,116–15,889 | 4.70 | 66 | 405.8 | ✓ |
| Astro | 0.33 | 8.68 | 5,446 | 5,372–5,714 | 14.02 | 141 | 478.9 | ✓ |
| Qwik | 34.79 | 34.41 | 1,176 | 1,174–1,183 | 75.28 | 153 | 251.3 | ✓ |
| React Router (Remix) | 113.19 | 12.86 | 1,076 | 1,042–1,137 | 59.22 | 172 | 378.7 | ✓ |
| Next.js | 134.55 | 17.43 | 687 | 674–689 | 97.08 | 323 | 5,049.4 | ✓ |

TTFB and p99 are the medians of the corresponding per-sweep percentiles, not
percentiles pooled across runs. Process start is the median of nine fresh process
starts per framework. Output sizes are qualified below. C/T/S = counter / theme /
search; theme persistence is also required.

## Versions and environment

| Entry | Measured versions |
|---|---|
| Next.js | Next 16.4.5; React / React DOM 19.3.1 |
| React Router (the Remix entry) | React Router / Node / Serve 8.5.1; React / React DOM 19.3.1; Vite 8.3.6 |
| Astro | Astro 7.4.6; @astrojs/node 11.1.10; Vite 8.3.6 |
| Qwik | Qwik / Qwik City 1.20.3; Vite 7.3.7; Express 4.22.2 |
| bext | Local production-runtime snapshot, version 0.2.9; exact binary/toolkit hashes below |

The four framework versions were checked against the npm registry's current
`latest` releases before installing. Qwik stays on its supported Vite 7 line.
Each package's lockfile records the resolved dependencies.

- AMD Ryzen 9 5900X: **12 physical cores / 24 logical CPUs**, shared Linux host.
- Node **v26.12.1**, npm **11.10.1**, oha **1.14.0**, Puppeteer **25.16.0**,
  Chrome **152.0.7977.75**.
- Measured app/harness source commit: `97453c9`. Per-file SHA-256 hashes are recorded
  as well, including all lockfiles. No instrumentation changed during the campaign.
- bext binary SHA-256: `83b854fe1274d44df46089f81b9e8c4185636b1e08031eeef71b747f266caa24`.
- bext toolkit tree SHA-256: `f5f38ffd3e72d19791ab88aab0b2cf92324e537d26f5e48c97096001c2d2bdba`.
  The toolkit file hashes are in the metadata. The binary and toolkit were copied
  to a private local snapshot before measuring; production services were not changed.
- Recorded one-minute load averages before/after entries ranged **4.77–7.74**.
  These samples are not a continuous CPU-utilization trace.

## Every measured run

| Framework | Sweep 1 | Sweep 2 | Sweep 3 |
|---|---:|---:|---:|
| bext (PRISM) | 15,889 | 15,874 | 15,116 |
| Astro | 5,372 | 5,714 | 5,446 |
| Qwik | 1,174 | 1,176 | 1,183 |
| React Router (Remix) | 1,042 | 1,137 | 1,076 |
| Next.js | 674 | 687 | 689 |

Sweep orders: Next → React Router → Astro → Qwik → bext; Astro → Qwik → bext →
Next → React Router; bext → Next → React Router → Astro → Qwik.

Across all 15 measured load tests: **578,520 HTTP 200 responses**, no non-200s,
no transport errors. There were **45 process-start samples**, 15 successful browser
checks, and **300 distinct under-load render samples** (20 within each entry).
Warmup traffic is separate from the measured response count.

## How to read these results

bext has the highest configured-server throughput in this workload: about
**2.9× Astro**, **13.5× Qwik**, **14.8× React Router**, and **23.1× Next.js**.
Astro ships the least JS at **0.33 KiB** using a vanilla DOM script. bext's three
resumable islands and shared runtime total **5.71 KiB**. These are measurements of
one small app, not general rankings of the frameworks.

TTFB is measured **under concurrency 50**. Qwik's p50 first byte is 34.41 ms; its
p99 response is 75.28 ms. Idle browser navigation timings are separate diagnostics
and do not replace this column.

The old headline selected the fastest of 9 Node runs and 15 bext runs. This report
uses medians of three equal sweeps; it also changes framework versions, Node,
startup launchers, output accounting, and waits for in-flight load requests. These
changes prevent a clean attribution of differences to framework improvements.
The [October writeup](../../results/history/2026-10-10.md) and its raw runs remain archived.
The README's stale June table has been replaced with this campaign.

## Measurement details and limits

Final audit corrected the descriptive `uniqueLoadUrls` metadata flag: oha selects
URLs with replacement. The correction and original flag value are recorded in
`metadataCorrections`; the requests, raw timings, cache configuration and results
were unchanged. Future runner metadata describes the URL pool explicitly.

- Every entry has a two-second warmup and an eight-second load test using
  `oha -z 8s -c 50 -w --http-version 1.1`. HTTP/1.1 keep-alive, with queries sampled
  randomly from one million distinct `?r=` URLs; individual URLs can repeat, as
  documented by [oha v1.14.0](https://github.com/hatoo/oha/blob/v1.14.0/README.md#urls-from-file-feature).
  Freshness relies on the uncached framework configuration and live timestamp
  checks. bext also sets `BEXT_PRISM_RENDER_CACHE=0` and
  uses the same admission-cap overrides as the October comparison (64 per worker,
  queue depth 256). Timestamp proof is collected during the actual measured load.
- bext uses its default pool of four V8 subprocesses. The Node entries use their
  normal single server process. This is a comparison of the configured servers,
  not throughput at equal CPU budgets or an equal-worker experiment.
- Client JS sums each distinct external JS resource compressed at gzip level 6
  and concatenated inline script bodies at the same level. Serialized inline data
  is included. Counting covers the initial visit and all three interactions, then
  stops before the persistence reload. Initial and post-interaction totals happened
  to be identical for all five entries in these runs.
- Process start means spawn to first complete HTTP 200, with warm OS/filesystem
  and compile caches. Three starts per framework per sweep; 5 ms polling. Local
  Node entrypoints are invoked directly. The former `npx` launcher overhead is
  absent, so October startup numbers are not directly comparable. This is not a
  cold-machine/deployment-time measurement.
- Node output sizes are actual file-byte sums: Next `.next` excluding compiler
  `cache` and `diagnostics`; React Router `build`; Astro `dist`; Qwik `dist` plus
  `server`. Only those output directories are counted; separate dependency installs
  and runtime executables are excluded.
- **bext's 405.8 KiB output is generated `.bext` runtime state**, including local
  SQLite databases/WAL files and route wrappers, measured while serving. It is
  not equivalent to the Node build artifacts and can vary as runtime state changes.
  Its external runtime binary and shared toolkit are excluded. The earlier fixed
  “~4 KB build” claim should not be read as a deployment footprint.
- No network or mobile CPU throttling. The post-settle click latency is diagnostic,
  not navigation-to-interactive; no TTI claim is made.
- Three short sweeps on a shared host provide a useful refresh and an observed
  range, not a confidence interval or an isolated-hardware capacity guarantee.

## Evidence and reproduction

- [Campaign status and run order](../../results/runs/2026-11-05/campaign.json)
- [Toolchain, source and runtime hashes](../../results/runs/2026-11-05/metadata.json)
- [Summary with all per-run metrics and startup samples](../../results/runs/2026-11-05/summary.json)
- [Sweep 1](../../results/runs/2026-11-05/run-1/), [sweep 2](../../results/runs/2026-11-05/run-2/),
  [sweep 3](../../results/runs/2026-11-05/run-3/): raw oha, warmup, browser, proof, output
  size and environment JSON for every entry.

[README reproduction commands](../../README.md#reproduce) and [SPEC.md](../../SPEC.md) describe
the contract. Failed or incomplete campaigns are not publishable, and occupied
ports are never cleared by killing existing processes.

Validation: all four production builds passed; Next's build type check and Qwik's
build type/lint checks passed; seven harness-integrity tests passed. The full
campaign passed the runtime contract for every entry in every sweep. All benchmark
processes were stopped after their measurements.
