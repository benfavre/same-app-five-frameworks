# Same App, Five Frameworks

The same 24-product SSR app, counter, persisted theme toggle, and live search in
Next.js, React Router (the Remix entry), Astro, Qwik, and bext. Every measured
request renders fresh HTML.

## Current results — equal CPU budget, 2026-11-05

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

## What is checked

- Fresh rendering: different idle timestamps plus 20 distinct timestamps sampled
  during each measured load test. oha samples from one million query URLs with
  replacement; bext's render-result cache is explicitly disabled.
- All 24 card elements and product names exist in the raw SSR HTML.
- A real browser increments the counter, toggles and persists the theme across a
  reload, filters the expected products with mixed-case input, and restores the
  complete list when the input is cleared. Every framework uses the same typing
  rate and waits for the asserted search DOM state.
- Every load response is HTTP 200, with no transport errors. The server process
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
  --bext-v8-workers 4 --bext-http-workers 1 \
  --output results/runs/local-one-cpu
npm run summarize -- results/runs/local-one-cpu --publish
```

Each output directory must be new. Occupied ports fail safely; the runner only
stops process groups it starts. `bash harness/run-all.sh` is equivalent to
`npm run benchmark`. Without CPU/worker options, the runner measures unrestricted
configured servers; label that separately from equal-CPU results.

To omit bext, add `--frameworks next remix astro qwik`. Override `--repeats`,
`--duration`, `--concurrency`, or `--cold-samples` as needed. Defaults are three
sweeps, three process starts per entry per sweep, a two-second warmup, then
`oha -z 8s -c 50 -w` with HTTP/1.1 keep-alive. The order rotates across sweeps.
`--publish` updates local results JSON; it does not push to GitHub.

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
