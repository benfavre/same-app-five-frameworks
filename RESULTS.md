# Same app, five frameworks — equal CPU budget, 2026-11-05

**The original headline was not an equal-CPU comparison.** bext's ~15,900 RPS
used four V8 subprocesses plus a multi-threaded HTTP/controller process with access
to all host CPUs. A fresh reproduction consumed about eight logical CPUs' worth of
CPU time. Counting four render workers alone understated its total CPU use.

The headline below gives every server process, child process and helper thread
**the same one-hardware-thread budget (CPU 10)**. Astro leads this comparison.
All five use the same app/dependencies/bext snapshot as the earlier November run.

## Equal-CPU results

| Framework | RPS median | RPS min–max | TTFB p50 | p99 | JS gzip | CPU ms/request |
|---|---:|---:|---:|---:|---:|---:|
| Astro | 4,290 | 4,169–4,336 | 9.93 ms | 36.89 ms | 0.33 KiB | 0.233 |
| bext (PRISM) | 2,102 | 2,079–2,175 | 22.94 ms | 65.00 ms | 5.71 KiB | 0.475 |
| Next.js | 448 | 441–453 | 28.63 ms | 170.24 ms | 134.55 KiB | 2.233 |
| Qwik | 415 | 365–417 | 95.86 ms | 187.43 ms | 34.79 KiB | 2.398 |
| React Router (Remix) | 369 | 365–378 | 39.72 ms | 190.14 ms | 113.19 KiB | 2.708 |

Three equal sweeps each, eight seconds at concurrency 50, after a two-second
warmup. RPS/TTFB/p99 are medians of per-sweep measurements; every sweep is retained.
TTFB is first-byte p50 **under load**. CPU ms/request uses sampled total server-tree
CPU time, so includes the small amount of proof traffic/background work.

All 15 entries passed all 24 SSR-product checks, counter/theme/search, theme
persistence, search reset, uncached idle/load proof, HTTP status checks, and CPU
affinity audits. **182,870 measured HTTP 200 responses, zero transport errors
or non-200s.** All server/helper-thread masks stayed within CPU 10.

bext's headline configuration retains four V8 workers but has one HTTP worker;
all share the same one logical CPU. A strict one-V8-worker control is shown below,
so the result does not depend on retaining multiple render processes.

## bext controls: CPU time, not worker count

| CPU affinity | V8 / HTTP workers | RPS median | RPS min–max | CPU seconds | Audit wall seconds | Avg logical CPUs occupied |
|---|---:|---:|---:|---:|---:|---:|
| CPU 10 only | 4 / 1 | 2,102 | 2,079–2,175 | 7.99 | 8.77 | 0.91 |
| CPU 10 only | 1 / 1 | 1,967 | 1,944–1,982 | 8.01 | 8.77 | 0.91 |
| CPU 10 only | 4 / 24 | 2,090 | 1,946–2,115 | 8.07 | 8.76 | 0.92 |
| All 24 logical CPUs allowed | 4 / 24 | 15,769 | 15,538–16,030 | 69.67 | 8.80 | 7.91 |

Each control has three complete, validated sweeps. CPU seconds, wall seconds and
occupied-CPU figures are medians of the individual measurements. “Logical CPUs
occupied” is summed server-tree CPU seconds divided by audit wall time; it does
not count worker processes or physical cores.

The decisive paired control keeps **four V8 workers and 24 HTTP workers** in both
cases. Changing CPU affinity from all 24 logical CPUs to CPU 10 reduced the median
from **15,769 to 2,090 RPS**, about **7.5×**.
This supports the conclusion that the previous high-throughput headline depended
heavily on access to more CPU. It was a configured-instance comparison, not
per-core evidence that bext renders faster than Astro.

With the same one-CPU budget, **Astro (4,290 RPS) is about
2.04× bext's four-worker result (2,102)**.
The one-V8-worker bext result is **1,967 RPS**. Pool size 1 uses a
different single-worker IPC dispatch path in this binary; showing both controls
avoids treating worker-count changes as a pure CPU-budget experiment. The paired
24-HTTP-worker comparison above changes only the requested CPU affinity.

In the first unrestricted audit, the controller/master consumed **37.25 CPU-seconds**
and the four V8 subprocesses about **8.1 CPU-seconds each**. That is why simply
dividing the original RPS by four would not correctly normalize total CPU use.
Node's GC/JIT helpers can also use other CPUs despite there being one Node server
process; affinity limits all of them in the new headline.

## Every headline run

| Framework | Sweep 1 | Sweep 2 | Sweep 3 |
|---|---:|---:|---:|
| Astro | 4,336 | 4,169 | 4,290 |
| bext (PRISM) | 2,079 | 2,102 | 2,175 |
| Next.js | 441 | 453 | 448 |
| Qwik | 365 | 417 | 415 |
| React Router (Remix) | 365 | 378 | 369 |

Orders: Next → React Router → Astro → Qwik → bext; Astro → Qwik → bext → Next →
React Router; bext → Next → React Router → Astro → Qwik. No best-run selection.

## CPU enforcement and measurement limits

- Linux `taskset` applies CPU 10 to each server before startup. Children and helper
  threads inherit the mask. During load, the audit samples the full descendant
  process tree every 250 ms and checks every thread's affinity. A mask escape,
  missing audit or audit error fails the campaign/summary.
- The benchmark runner, oha and browser are restricted to CPUs
  `0-9,11-21,23`, excluding both CPU 10 and its SMT sibling CPU 22. This is the same
  client mask for every CPU-controlled experiment and for the new unrestricted
  bext control.
- CPU 10 is **one hardware thread**, not both SMT threads of a physical core.
  Affinity does not reserve an exclusive core on this shared machine. Other host
  work, SMT sibling activity, power/frequency changes and cache effects can still
  affect results. Three short sweeps give observed ranges, not confidence bounds.
- CPU accounting sums each observed process's own user+system ticks from `/proc`;
  child CPU is counted from child processes, not added again from the parent's
  child-time fields. The clock is 100 Hz on this host. Process counts stayed stable
  during these load tests. Very short-lived unobserved children would not be a
  precise profiler trace.
- The audit window starts before spawning oha and includes its URL-file parsing
  and final accounting, so it is roughly 8.8 seconds for an eight-second load.
  This explains the ~0.91 occupied-CPU average in the one-CPU runs. The actual
  CPU-affinity cap remains one throughout.

## Versions and identical inputs

| Entry | Measured versions |
|---|---|
| Next.js | Next 16.4.5; React / React DOM 19.3.1 |
| React Router (Remix entry) | React Router / Node / Serve 8.5.1; React / React DOM 19.3.1; Vite 8.3.6 |
| Astro | Astro 7.4.6; @astrojs/node 11.1.10; Vite 8.3.6 |
| Qwik | Qwik / Qwik City 1.20.3; Vite 7.3.7; Express 4.22.2 |
| bext | Local runtime snapshot 0.2.9, same exact binary and toolkit as the unrestricted run |

Host: AMD Ryzen 9 5900X, 12 physical cores / 24 logical CPUs, shared Linux activ-2.
Node v26.12.1; npm 11.10.1; oha 1.14.0; Puppeteer 25.16.0; Chrome 152.0.7977.75.

Measurement source commit: `56ec45a5819ef982f28f493aae36f6c2e0c3116d`; per-file source and
lockfile hashes are recorded in each campaign's metadata. The app code was not
changed for this CPU comparison. No measurement instrumentation changed between
the four completed CPU campaigns. CPU captions were added to the table formatter
after the experiments.

bext binary SHA-256: `83b854fe1274d44df46089f81b9e8c4185636b1e08031eeef71b747f266caa24`.
Toolkit tree SHA-256: `f5f38ffd3e72d19791ab88aab0b2cf92324e537d26f5e48c97096001c2d2bdba`.
Production services and their CPU allocation were not changed.

## Other protocol details

- `oha -z 8s -c 50 -w --http-version 1.1`, keep-alive, all responses must be HTTP
  200, successRate=1 and errorDistribution empty. Every load is preceded by a
  two-second warmup. Framework response caches are disabled, including bext's
  `BEXT_PRISM_RENDER_CACHE=0`; admission overrides remain cap 64 / queue 256.
- oha randomly samples one million distinct query URLs **with replacement**;
  individual request URLs can repeat. Freshness relies on uncached configuration
  and timestamp checks during the actual load, not guaranteed URL uniqueness.
- Client JS uses the same gzip level 6 for every distinct external JS resource
  plus concatenated inline script bodies, including serialized data. It covers
  initial visit and all three interactions, stopping before the persistence reload.
  Astro uses vanilla DOM scripting; the other entries include their reactive or
  resume runtimes. KiB means 1,024 bytes.
- Process start is median of nine spawn-to-first-complete-200 samples per framework
  with warm filesystem/compile caches and direct local launchers. No cold-machine,
  mobile-throttled or navigation-to-interactive claim is made.
- Output sizes in the machine-readable summary count Next `.next` excluding
  compiler `cache` and `diagnostics`, React Router `build`, Astro `dist`, and Qwik
  `dist` plus `server`. Separate dependencies/runtime executables are excluded.
  bext's `.bext` output includes runtime databases/WAL and wrappers, so it is not
  equivalent to a Node deployment artifact or a total deployment footprint.

## Rejected attempt and evidence

The first CPU campaign was rejected when Qwik's search check reported zero cards
instead of three. It remains [recorded as failed](results/runs/2026-11-05-one-cpu/campaign.json).
The browser tester now types at the same 50 ms/character rate for every entry,
waits up to five seconds for the expected search DOM state, and records the actual
query. It still fails if the query or result count is wrong. This changes the
post-load functional-check protocol, not the timed HTTP load. All completed CPU
campaigns use that same tester; the failed attempt is not included in medians.

- [Headline: every framework on one CPU](results/runs/2026-11-05-one-cpu-final/)
- [bext: one V8 / one HTTP worker on one CPU](results/runs/2026-11-05-one-cpu-one-v8/)
- [bext: original four V8 / 24 HTTP workers on one CPU](results/runs/2026-11-05-bext-original-one-cpu/)
- [bext: original worker settings with all CPUs allowed](results/runs/2026-11-05-bext-original-cpu-audit/)
- [Earlier unrestricted November writeup](results/history/2026-11-05-configured-servers.md)
- [October writeup](results/history/2026-10-10.md)

The four completed CPU campaigns contain **24 validated load/browser entries**,
**658,451 measured HTTP 200 responses**, no load errors, and no CPU-affinity
violations. The four production builds previously passed; ten harness-integrity
tests now include CPU-mask escape detection, child CPU accounting, and rejection
of missing/invalid audits. All benchmark processes were stopped.

[README reproduction commands](README.md#reproduce) and [SPEC.md](SPEC.md) describe
the contract. The latest published JSON points to the equal-CPU headline campaign.

## Profile-guided improvement: prepared page setup

A follow-up asks how to close bext's equal-CPU gap. The first measured improvement
reuses prepared route/compiler inputs, without caching rendered HTML or changing
the fixture. `BEXT_PRISM_PREPARED_PAGES=1` is an existing opt-in path; this experiment
does not change the engine binary or production configuration.

Three paired groups ran in **AB / BA / AB** order (A=control, B=prepared). Every
process uses CPU 10, four V8 workers, one HTTP worker, multiplex explicitly off,
render-result caching off, and the same binary, toolkit and app inputs. Each load
is eight seconds at concurrency 50 after the same two-second warmup.

| Mode | RPS median | RPS range | CPU ms/request | p99 median |
|---|---:|---:|---:|---:|
| control | 2,156 | 2,136–2,190 | 0.4613 | 67.10 ms |
| prepared | 2,587 | 2,581–2,642 | 0.3902 | 39.63 ms |

The ratio of medians is **20.0% more throughput** and
**15.4% less CPU per request**. The three paired RPS increases
were 22.5%, 17.8% and 21.1%.
These are three groups on a shared host, not a confidence interval or universal
speed guarantee. All six load/browser/CPU/fresh-render checks passed, covering
114,528 measured HTTP 200 responses with no load errors or affinity violations.

The independent preliminary screen is retained: control 2,170; prepared 2,620;
multiplex alone 2,083; both 2,624 RPS. Multiplexing alone did not improve throughput,
and the combined mode did not establish a useful gain over preparation alone, so
only preparation was taken into the paired confirmation. No screen run is used
as the confirmation result.

The native CPU profile contained 2,220 samples, zero lost, from only the benchmark
server and its four children on one CPU. It found 9.86% self time in BLAKE3 hashing,
4.73% in Unicode lowercasing, 3.33% in V8-to-Rust string conversion, and 4.77%
inclusive time in wrapper preparation. Inclusive/descendant costs overlap and
must not be added. Profiling perturbs timing; the speed figures above are from
separate unprofiled processes.

The frozen baseline's legacy `EvalThreadState::process_request` ignores the provided
bundle hash and recomputes cache keys. The multiplex path already consumes that
identity, but changing dispatcher mode also changes scheduling costs; its losing
screen shows why the narrower hash-reuse change is a better next experiment.

The [source-invalidation probe](results/experiments/2026-11-05-bext-preparation/source-freshness.json)
passed **14 cases** across preparation off/on: initial render, page edit, layout
edit, imported-data edit, layout deletion, layout re-addition, and a fresh render
timestamp afterward. It uses disposable fixture copies with `live_reload=true`
and waits for the watcher's first one-second baseline scan. Timed performance
runs keep `live_reload=false`. Two setup failures remain recorded: the initial
probe with watching disabled, then a probe that edited before the initial watcher
snapshot. Neither failed setup is represented as a successful invalidation check.

Preparation still does **not** lead Astro: 2,587 versus the CPU-controlled
reference's 4,290 RPS. Its 0.390 CPU ms/request must fall by roughly
**40% further**, to below Astro's 0.233, to match that reference
on this fixed workload.

The engineering priorities at that checkpoint were, in order:

1. Make a prepared execution plan the normal warm path: retain immutable route,
   wrapper, alias and compiled-function metadata while keeping request props,
   loaders and HTML fresh. The measured preparation gain supports this direction;
   broader invalidation and memory checks are needed before changing defaults.
2. Honor the precomputed bundle identity on the legacy evaluation path, with
   fallback hashing when absent and tests for changed bundles/shells. This targets
   the observed hashing cost without switching to the slower dispatcher mode.
3. Remove repeated whole-document Unicode case folding and intermediate string
   conversions; scan ASCII tag names and carry owned UTF-8 output through to HTTP.
   Preserve Unicode, streaming, metadata and CSP behavior in the shared paths.
4. Profile and reduce controller/worker allocations and handoffs after those
   changes. The original CPU split was about half controller, half V8 workers, so
   renderer-only micro-optimizations cannot remove all of the gap.

Reproduce the candidate with the normal one-CPU command plus
`--bext-flag BEXT_PRISM_PREPARED_PAGES=1 --bext-flag BEXT_V8_MULTIPLEX=0`.
Run `python3 harness/check-prepared-source.py --output /path/to/freshness.json` for
the disposable source check (same BEXT_BIN/BEXT_SHARED_FRAMEWORK_DIR environment).
Only allowlisted performance settings can be passed through the harness;
response-cache flags are excluded from that option.

Evidence: [preliminary modes](results/experiments/2026-11-05-bext-preliminary/),
[paired manifest and runs](results/experiments/2026-11-05-bext-preparation/),
[analysis JSON](results/experiments/2026-11-05-bext-preparation/analysis.json), and
[profile summary](results/experiments/2026-11-05-bext-preparation/profile.json).
The raw 18 MiB perf trace is retained locally at the path/hash in that summary.
The primary results JSON and headline remain the default equal-CPU comparison;
this opt-in improvement is a separately labeled experiment.

## Native hash reuse and recovered scanner/text paths

The legacy V8 driver now has an opt-in patch to honor the bundle identity already
supplied by its worker: [bext PR #420](https://github.com/benfavre/bext/pull/420).
Missing identities still hash the code. Page/API cache namespaces, shell identity,
changed-code invalidation and per-request execution remain intact. This reuses
code identity, never rendered responses. The flag defaults off.

The canonical 18-feature PHP-ZTS release build passed, with unchanged private
source and external-dependency fingerprints. Its SHA-256 is
`964164876c0ca891595e6234ffa3fbb9bbdbe735ac622b09275c910c0e127ed7`.
The release V8 suite passed **228 tests**, zero failed, four pre-existing ignored.
Five new tests cover hash fallback/reuse, fresh page/API data, changed code and
shell changes. The [build provenance](results/experiments/2026-11-05-bext-native-hash/build-provenance.json)
links the recovered source and focused patch commits to the artifact.

Nine fresh process runs use balanced **ABC / BCA / CAB** order: A=frozen native83,
B=rebuilt with hash reuse off, C=the same rebuilt binary with reuse on. Preparation
is on and multiplex off throughout. All processes/threads share CPU10; clients
exclude it and its SMT sibling. Every run retains the same eight-second,
50-connection load, frozen SDK/app, two-second warmup, browser interactions,
24 SSR products, fresh render timestamps and strict HTTP200/affinity checks.

| Mode | RPS median | RPS range | CPU ms/request | p99 median |
|---|---:|---:|---:|---:|
| Frozen native83, prepared | 2,570 | 2,440–2,594 | 0.3929 | 40.49 ms |
| Rebuilt, hash reuse off | 2,576 | 2,333–2,625 | 0.3931 | 40.59 ms |
| Rebuilt, hash reuse on | 2,968 | 2,730–3,113 | 0.3379 | 37.00 ms |

Hash reuse gives **15.2% more median throughput** and **14.0% less CPU/request**
against its same-artifact control. The three paired RPS gains are 33.4%, 6.0% and
13.1%; shared-host variation is material. These are descriptive three-block
measurements, not confidence intervals. The frozen release remains a separate
control, so unrelated rebuild changes cannot silently stand in for the patch.

[Same-artifact diagnostic profiles](results/experiments/2026-11-05-bext-native-hash/profiles/profile.json)
show BLAKE3 AVX2 self time at **13.36% off**, absent above the report's **0.25%**
threshold on. These instrumented runs are excluded from throughput summaries.
[Off](results/experiments/2026-11-05-bext-native-hash/source-freshness-0.json) and
[on](results/experiments/2026-11-05-bext-native-hash/source-freshness-1.json) source
checks pass **36 cases**, including page/layout/import edits, layout deletion and
re-addition, fresh render stamps, and **192 GET/POST probes** for changing API
source and request data. All source edits occur in disposable copies.

A separate corrected screen tested existing token scanning, prepared text mode2
and native HTML scanning. An independent **AB / BA / AB** confirmation compares
hash/preparation alone with their combination; process isolation and the default
pool/shared-memory/async transport are unchanged.

| Mode | RPS median | CPU ms/request | p99 median |
|---|---:|---:|---:|
| Hash + preparation | 3,053 | 0.3295 | 33.37 ms |
| Plus scanner1 / text2 / native HTML1 | 3,406 | 0.2962 | 31.02 ms |

The second comparison adds **11.6% throughput** and reduces CPU/request **10.1%**;
all three paired RPS gains are positive (4.6%, 13.0%, 12.3%). The confirmation
result is separate from the exploratory screen's fastest run. Its complete
[screen and confirmation evidence](results/experiments/2026-11-05-bext-existing-flags-corrected/)
is retained. The combined mode still trails Astro's earlier **4,290 RPS**
reference; it has not established a lead or production rollout qualification.

The initial [transport screen](results/experiments/2026-11-05-bext-existing-flags/screen.json)
failed and is retained. Explicitly setting `BEXT_V8_SUBPROCESS=1` bypasses the
standalone bootstrap that supplies `POOL=1`, `SHM_IPC=1` and `ASYNC_EVAL=1`;
this accidentally selected the older serialized path. Its controls crashed in
`tracing_subscriber::Subscriber::try_close`. An in-process diagnostic also
crashed and is excluded. Successful cases in that failed screen are not evidence
for the corrected combination. The harness no longer accepts the transport
override. No failed run is published as a pass.

The history audit found all three `perf/*` branches already merged into local
and GitHub master. The missing native work was in a November4 WIP snapshot.
[Draft recovery PR #419](https://github.com/benfavre/bext/pull/419) preserves 81
native paths, 19 SDK source paths and qualification notes without publishing
the snapshot's unrelated application files/artifacts. The two master histories
diverge, and their whole-tree merge has 100 conflicts. Recovery needs deliberate
native/SDK reconciliation; failed historical experiments retain their original
opt-in behavior and are not activated by a source push.

No production binary, configuration or service changed. The headline/default
equal-CPU campaign and `results/latest.json` remain unchanged; these are labeled
optimization experiments.

An eight-case [nursery/worker screen](results/experiments/2026-11-05-bext-nursery-workers/screen.json)
tested one/two/four V8 workers and 4/8MiB nursery limits on the same single CPU.
The selected two-worker/4MiB case subsequently confirmed at 3,444 versus 3,389 RPS
(+1.6%), with one pair using slightly more CPU. This small, variable increment
does not justify replacing the established four-worker/default-nursery setup.

A separate [detailed-tracing comparison](results/experiments/2026-11-05-bext-tracing/analysis.json)
uses `--bext-log-filter warn` with the established four-worker combination.
It records 3,312 -> 3,517 median RPS (+6.2%) and 0.3032 -> 0.2857 CPU ms/request
(-5.8%). All three paired throughput gains are positive (6.7%, 5.0%, 5.5%).
This is an observability tradeoff: detailed Rust tracing is reduced. The runner
separately counts complete HTTP access-log records and verifies they remain
present for every measured request; no render/cache/CPU-budget work is skipped.
The continuous profiler retains its existing default. This configuration gain
is kept separate from the native hash and scanner/text contributions.

The combined scanner/text mode also passes
[18 further source/API freshness cases](results/experiments/2026-11-05-bext-existing-flags-corrected/source-freshness-combined.json)
and [34 SDK regressions / 351 assertions](results/experiments/2026-11-05-bext-existing-flags-corrected/sdk-regressions.json),
covering Unicode/mixed-case metadata, buffered/streaming output and async callback
ordering. No HTTP access-logging or process-isolation tradeoff is made by those
code-path settings.

## Fresh five-framework sweep with the Bext candidate

The final candidate sweep reruns **all five frameworks**, with three rotating
sweeps, three process starts per entry, the same eight-second/50-connection load
and one logical CPU for each entire server tree. Bext uses the new native binary,
the same frozen SDK/app, preparation/hash/scanner/text/native-HTML settings above,
four V8 workers, one HTTP worker, the default nursery/transport and `RUST_LOG=warn`.
HTTP access logging remains enabled. The other four entries retain their normal
production configurations. This is an opt-in Bext candidate, not a new default.

| Framework | RPS median | RPS range | CPU ms/request | p99 median |
|---|---:|---:|---:|---:|
| Astro | 4,252 | 4,179–4,299 | 0.2346 | 37.58 ms |
| bext candidate | 3,469 | 3,448–3,477 | 0.2902 | 31.78 ms |
| Next.js | 443 | 441–452 | 2.2512 | 181.36 ms |
| Qwik | 401 | 394–430 | 2.4846 | 187.89 ms |
| React Router | 359 | 355–364 | 2.7868 | 199.21 ms |

All **15 load/browser entries** pass, covering **214,542 measured HTTP200
responses**, zero load errors and zero CPU-affinity violations. Counter, theme,
theme persistence, mixed-case search/reset, all24 SSR products and changing
render stamps pass for each entry. [Raw campaign](results/experiments/2026-11-05-five-frameworks-bext-candidate/),
[summary JSON](results/experiments/2026-11-05-five-frameworks-bext-candidate/summary.json)
and [full table](results/experiments/2026-11-05-five-frameworks-bext-candidate/table.md)
retain versions, binary/SDK/source identities and explicit configuration.

Bext remains second in throughput. Matching this contemporary Astro reference
requires about **22.6% more throughput**, or **19.2% less CPU/request** than this
candidate. The lower observed Bext p99 is a separate short-run measurement, not
a throughput lead or a general tail-latency guarantee. The next profiling target
is controller/worker allocation, string ownership and handoff overhead after the
now-measured hash and scanner/text costs; tuning the nursery did not close it.

## Merged-source refresh and rejected follow-ups, 2026-11-06

Bext uses the merged native/SDK source, the documented opt-in preparation/hash/scanner/text settings, and `--bext-log-filter warn`. HTTP access logging stays enabled. Each complete server tree shares CPU 10; clients exclude that physical core and its SMT sibling. Three rotating eight-second sweeps at concurrency 50:

| Framework | RPS median | RPS min–max | CPU ms/request | p99 |
|---|---:|---:|---:|---:|
| Astro | 3,993 | 3,853–4,275 | 0.2501 | 41.02 ms |
| bext (PRISM) | 3,530 | 3,407–3,541 | 0.2866 | 30.31 ms |
| Qwik | 442 | 437–442 | 2.2644 | 171.34 ms |
| Next.js | 428 | 418–451 | 2.3363 | 182.06 ms |
| React Router (Remix) | 367 | 361–391 | 2.7205 | 197.46 ms |

**Astro remains ahead in throughput.** All 15 load/browser entries passed: 211,132 measured HTTP 200 responses, zero load errors and zero CPU-affinity violations. Counter, persisted theme, search/reset, 24-product SSR and fresh render stamps pass for every entry. These short shared-host runs show observed variation, not confidence intervals.

[Raw campaign and identities](results/experiments/2026-11-06-five-frameworks-merged/), [summary](results/experiments/2026-11-06-five-frameworks-merged/summary.json), [qualification](results/experiments/2026-11-06-five-frameworks-merged/qualification.json). The [rejected response-writer experiment](results/experiments/2026-11-05-bext-reply-transport/table.md) and [text-conversion screen](results/experiments/2026-11-06-bext-text-modes/table.md) are retained. The default-settings baseline remains archived in `results/latest.json`.


The new shared-memory response writer regressed independent AB/BA/AB confirmation by 2.16% RPS and raised CPU/request 2.38%; Bext PR #421 is closed without merging. Existing sized/native-copy text modes also lost their exploratory screen, so compact mode 2 remains selected. Source/correctness checks passing are kept separate from these failed performance results.

## Steady comparison with longer warmup, 2026-11-06

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

The [response-writer experiment](results/experiments/2026-11-05-bext-reply-transport/table.md), [reply-read-buffer trial](results/experiments/2026-11-06-bext-read-buffer/table.md), [direct-props serializer trial](results/experiments/2026-11-06-bext-direct-props/table.md) and [text-conversion screen](results/experiments/2026-11-06-bext-text-modes/table.md) did not improve performance and remain unselected. The earlier default-settings baseline remains archived; `results/latest.json` continues to identify that baseline.

The two-second-warmup figures above remain historical. The profiler-startup probe and updated input metadata accompany this campaign; the change in warmup applies equally to every framework.

## Bext PRISM — full-machine throughput, 2026-11-06

All 24 logical CPUs of the Ryzen 9 5900X (12 physical cores) are available to the server tree. Three runs per row, 20-second warmup and 15-second loads; fresh rendering, continuous profiling and HTTP access logging stay enabled. Clients share the machine.

| V8 / HTTP workers | Connections | RPS median | RPS min–max | Server CPU equivalents | CPU ms/request | p99 |
|---|---:|---:|---:|---:|---:|---:|
| 4 / 1 | 50 | 10,969 | 10,928–11,122 | 2.77 | 0.2684 | 7.15 ms |
| 12 / 12 | 50 | 36,118 | 35,538–37,254 | 14.02 | 0.4128 | 3.23 ms |
| 16 / 24 | 50 | 34,734 | 34,217–38,144 | 14.59 | 0.4436 | 3.56 ms |

All 9 completed load/browser entries passed: 3,736,457 measured HTTP 200 responses, no load errors or CPU-affinity violations. These configured-instance figures have a different CPU budget from the equal-CPU comparison above. **The separate 200-connection check failed with HTTP 503 responses** (about 17% during warmup); no throughput result from that attempt qualifies. Observed ranges are not confidence intervals. [Method, reproduction and raw evidence](results/experiments/2026-11-06-bext-prism-multicore/notes.md).

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
