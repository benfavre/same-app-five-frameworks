# Same App, Five Frameworks

The same 24-product SSR app, counter, persisted theme toggle, and live search in
Next.js, React Router (the Remix entry), Astro, Qwik, and bext. Every measured
request renders fresh HTML.

## Latest tuned comparison — equal CPU budget, 2026-11-06

Every framework receives **20 seconds of warmup**, followed by an eight-second load at concurrency 50, repeated in three rotating sweeps. This passes the observed delayed profiler initialization in Bext; continuous profiling and HTTP access logging remain enabled. Bext uses the merged native/SDK source, documented opt-in preparation/hash/scanner/text settings and `--bext-log-filter warn`. Every complete server tree shares CPU 10; clients exclude that physical core and its SMT sibling.

| Framework | RPS median | RPS min–max | CPU ms/request | p99 |
|---|---:|---:|---:|---:|
| Astro | 4,975 | 4,665–5,165 | 0.2007 | 29.13 ms |
| bext (PRISM) | 3,732 | 3,370–3,844 | 0.2680 | 31.45 ms |
| Next.js | 482 | 478–507 | 2.0719 | 165.01 ms |
| Qwik | 471 | 468–486 | 2.1184 | 164.32 ms |
| React Router (Remix) | 368 | 360–379 | 2.7073 | 203.17 ms |

**Astro remains ahead in throughput.** All 15 load/browser entries passed: 238,454 measured HTTP 200 responses, zero load errors and zero CPU-affinity violations. Counter, persisted theme, search/reset, 24-product SSR and fresh render stamps pass for every entry. These short shared-host runs show observed variation, not confidence intervals.

[Raw campaign and identities](results/experiments/2026-11-06-five-frameworks-steady/), [summary](results/experiments/2026-11-06-five-frameworks-steady/summary.json), [qualification](results/experiments/2026-11-06-five-frameworks-steady/qualification.json). The [earlier two-second-warmup comparison](results/experiments/2026-11-06-five-frameworks-merged/notes.md) remains archived. All frameworks benefited from the longer warmup; this is a measurement-method change, not a Bext code speedup.

The [response-writer experiment](results/experiments/2026-11-05-bext-reply-transport/table.md), [reply-read-buffer trial](results/experiments/2026-11-06-bext-read-buffer/table.md), [direct-props serializer trial](results/experiments/2026-11-06-bext-direct-props/table.md) and [text-conversion screen](results/experiments/2026-11-06-bext-text-modes/table.md) did not improve performance and remain unselected. The [profiler-startup probe](results/experiments/2026-11-06-bext-profiler-startup/notes.md) explains the longer warmup; a [JavaScript profiling helper](https://github.com/benfavre/bext/pull/423) is merged with [sample output](results/experiments/2026-11-06-bext-jit-profile/notes.md). The earlier default-settings baseline follows; `results/latest.json` continues to identify that baseline.

## Bext PRISM — full-machine throughput, 2026-11-06

The [admission fix](https://github.com/benfavre/bext/pull/430) queues brief per-site contention instead of immediately returning 503. The default wait is 250 ms with at most 256 waiting requests per site; existing fair-share and pool limits remain in force. A full queue or expired deadline still returns 503 + Retry-After.

All 24 logical CPUs of the Ryzen 9 5900X (12 physical cores) are available to the entire server tree. Clients share the host. Three fresh-server runs per row, 20-second warmup and 15-second loads; fresh rendering, continuous profiling and HTTP access logging stay enabled.

| Runtime | V8 / HTTP | Connections | Median RPS | RPS min–max | Server CPU equivalents | p99 |
|---|---|---:|---:|---:|---:|---:|
| Original immediate admission | 12 / 12 | 50 | 36,862 | 30,829–38,401 | 14.34 | 2.88 ms |
| Bounded admission wait | 12 / 12 | 50 | 36,652 | 35,303–36,764 | 14.12 | 3.05 ms |
| Bounded admission wait | 16 / 24 | 200 | 25,969 | 24,990–27,563 | 11.51 | 11.82 ms |

With the wait enabled, **all six entries passed: 3,658,428 warmup and 2,809,837 measured HTTP 200 responses, zero warmup/load errors**. All three 200-connection runs passed browser/SSR/freshness checks. At 50 connections, observed median throughput changed −0.57% and p99 changed from 2.88 to 3.05 ms; this is a correctness fix, not a speedup claim. The 50-connection comparison uses balanced AB/BA/AB ordering. These shared-host ranges are not confidence intervals.

Waiting disabled on the same rebuilt binary reproduced 152,122 warmup 503 responses. That failed control and the [earlier full-machine pool sizing and failed overload attempt](results/experiments/2026-11-06-bext-prism-multicore/notes.md) remain archived. New campaigns reject non-200 warmup responses and publication rechecks that evidence. [Method, raw evidence and identities](results/experiments/2026-11-06-bext-site-admission-wait/notes.md). The one-CPU comparison above uses its separately pinned runtime and CPU budget.

## Default-settings baseline — equal CPU budget, 2026-11-05

**Every server, child process and helper thread is pinned to one hardware thread
(CPU 10).** The load generator is kept off that physical core and its SMT sibling.
Three equal eight-second sweeps per framework, concurrency 50; medians and every
sweep's range below. All raw data, including CPU affinity audits, is retained.

| Framework | Version | RPS median | RPS min–max | TTFB p50 | p99 | JS gzip |
|---|---|---:|---:|---:|---:|---:|
| Astro | 7.4.6 | 4,290 | 4,169–4,336 | 9.93 ms | 36.89 ms | 0.33 KiB |
| bext (PRISM) | 0.2.9* | 2,102 | 2,079–2,175 | 22.94 ms | 65.00 ms | 5.71 KiB |
| Next.js | 16.4.5 | 448 | 441–453 | 28.63 ms | 170.24 ms | 134.55 KiB |
| Qwik | 1.20.3 | 415 | 365–417 | 95.86 ms | 187.43 ms | 34.79 KiB |
| React Router (Remix) | 8.5.1 | 369 | 365–378 | 39.72 ms | 190.14 ms | 113.19 KiB |

*The local bext runtime/toolkit is identified by exact SHA-256 hashes in the
[metadata](results/runs/2026-11-05-one-cpu-final/metadata.json). Its four V8 workers
and one HTTP worker all share the same single CPU. A separate one-V8-worker
control and unrestricted configured-server control are in [RESULTS.md](RESULTS.md).

**Astro leads this equal-CPU comparison.** The previous ~15,900-RPS bext headline
used an unrestricted multi-core configuration. A fresh reproduction of that
configuration consumed about eight CPUs' worth of server CPU time. The original
[configured-server writeup](results/history/2026-11-05-configured-servers.md)
remains archived; those numbers are not per-core results.

Measured on shared activ-2: AMD Ryzen 9 5900X (12 physical cores / 24 logical CPUs),
Node v26.12.1, oha 1.14.0, Puppeteer 25.16.0, Chrome 152.0.7977.75. Affinity imposes
a CPU-access limit; it does not reserve an exclusive core on a shared host. One
Node process can use helper threads, so process counts alone do not define a CPU
budget. TTFB and p99 here are measured under load.

A separate [profile-guided experiment](RESULTS.md#profile-guided-improvement-prepared-page-setup)
measured **2,156 → 2,587 RPS (+20%)** by reusing prepared route/compiler setup,
with no extra CPU or rendered-response caching. It passes source-invalidation
checks but still trails Astro; it is an opt-in result, separate from the headline.

## What is checked

- Fresh rendering: different idle timestamps plus 20 distinct timestamps sampled
  during each measured load test. oha samples from one million query URLs with
  replacement; bext's render-result cache is explicitly disabled.
- All 24 card elements and product names exist in the raw SSR HTML.
- A real browser increments the counter, toggles and persists the theme across a
  reload, filters the expected products with mixed-case input, and restores the
  complete list when the input is cleared. Every framework uses the same typing
  rate and waits for the asserted search DOM state.
- Every warmup and load response is HTTP 200, with no transport errors. The server process
  tree and every thread's affinity are sampled during the load interval. Missing
  or failed evidence, including an escaped CPU mask, prevents publication.

## Reproduce

Requires Linux with `taskset`, Node >=22.23.4, npm, Python 3, oha and Chrome.
Puppeteer downloads a compatible browser during installation;
`CHROME=/path/to/chrome` overrides it.

```bash
npm ci
for fw in next remix astro qwik; do
  (cd "apps/$fw" && npm ci && npm run build) || exit 1
done

export BEXT_BIN=/absolute/path/to/bext-server
export BEXT_SHARED_FRAMEWORK_DIR=/absolute/path/to/bext/sites/shared/framework

# CPU IDs below are for activ-2. Choose available IDs on another host;
# keep the server CPU and its SMT sibling out of the client mask.
npm run benchmark -- --server-cpus 10 --client-cpus 0-9,11-21,23 \
  --bext-v8-workers 4 --bext-http-workers 1 --warmup-seconds 20 \
  --output results/runs/local-one-cpu
npm run summarize -- results/runs/local-one-cpu --publish
```

Each output directory must be new. Occupied ports fail safely; the runner only
stops process groups it starts. `bash harness/run-all.sh` is equivalent to
`npm run benchmark`. Without CPU/worker options, the runner measures unrestricted
configured servers; label that separately from equal-CPU results.

To omit bext, add `--frameworks next remix astro qwik`. Override `--repeats`,
`--duration`, `--warmup-seconds`, `--concurrency`, or `--cold-samples` as needed. Defaults are three
sweeps, three process starts per entry per sweep, a legacy two-second warmup, then
`oha -z 8s -c 50 -w` with HTTP/1.1 keep-alive. The order rotates across sweeps.
`--warmup-seconds 20` is used for the latest steady comparison. `--publish`
updates local results JSON; it does not push to GitHub.

The recovered native/SDK source and measured hash improvement are merged in
[bext PR #419](https://github.com/benfavre/bext/pull/419) and
[PR #420](https://github.com/benfavre/bext/pull/420). Build merged master and add
these settings to the one-CPU command:

```bash
--bext-flag BEXT_PRISM_PREPARED_PAGES=1 --bext-flag BEXT_V8_MULTIPLEX=0 \
--bext-flag BEXT_V8_LEGACY_HASH_HINT=1 --bext-flag BEXT_PRISM_TOKEN_SCAN=1 \
--bext-flag BEXT_V8_PREPARED_TEXT=2 --bext-flag BEXT_PRISM_NATIVE_HTML_SCAN=1
```

Keep the same frozen SDK while comparing native binaries. To separate a rebuild
from its opt-in change, use the balanced three-block runner:

```bash
python3 harness/compare-bext-binaries.py --original /path/to/frozen-bext-server \
  --candidate /path/to/rebuilt-bext-server --framework /path/to/frozen-sdk \
  --output results/experiments/local-native-comparison
```

`harness/check-prepared-source.py --legacy-hash-hint 1 --output /path/to/proof.json`
checks page/layout/import/API invalidation and fresh request data in disposable
fixtures. Performance settings are allowlisted; response-cache and process-isolation
overrides are excluded. Reply-writer modes are separately allowlisted only to
reproduce the [rejected transport experiment](results/experiments/2026-11-05-bext-reply-transport/table.md);
they require the unmerged prototype. The reply-read-buffer and direct-props flags
also require their unmerged prototypes ([PR #422](https://github.com/benfavre/bext/pull/422)
and [PR #424](https://github.com/benfavre/bext/pull/424)); both trials were rejected.
Preserve the standalone defaults: setting
`BEXT_V8_SUBPROCESS=1` explicitly skips other standalone defaults in this version.
`--bext-log-filter warn` records a separate detailed-tracing tradeoff; HTTP access
logging is still checked. The [latest merged-source comparison](results/experiments/2026-11-06-five-frameworks-steady/table.md)
measures Bext at 3,732 versus Astro at 4,975 RPS on one CPU. The archived default
baseline remains separate from these opt-in measurements.

## Measurements and limits

Client JS uses uniform gzip level 6 for each external JS resource plus concatenated
inline script bodies, including serialized data. It includes code fetched during
the three interactions; counting stops before the persistence reload. KiB means
1,024 bytes. Astro uses a small vanilla DOM script; the other entries ship their
reactive/resume runtimes.

Process start is spawn-to-first-complete-200 with warm filesystem/compilation
caches, without `npx` overhead. Output sizes exclude separate dependency installs
and server/runtime executables; bext's `.bext` runtime-state directory is not
equivalent to a Node build artifact. No mobile-throttling or navigation-to-
interactive claim is made. Three short sweeps on a shared host show observed
ranges, not confidence intervals.

[Canonical contract](SPEC.md), [CPU-controlled evidence](results/runs/2026-11-05-one-cpu-final/),
and [detailed results and controls](RESULTS.md). Harness integrity tests:
`python3 -m unittest discover -s harness -p 'test_*.py'`.

MIT licensed.
