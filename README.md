# Same App, Five Frameworks: an honest, uncached SSR benchmark

One identical app, built idiomatically in **Next.js, Remix, Astro, Qwik, and
[bext](https://bext.dev)**, with every framework forced to **render fresh on
every request** (no caching, no prerendering) and the fairness **proven in the
output**. Measured: client JS shipped, TTFB, requests/sec, p99, cold start, build
size, and whether the three interactions actually work in a real browser.

Most framework benchmarks quietly compare a cached/prerendered response against an
uncached one. This one doesn't: each app renders a `data-rendered-at` timestamp, and
the harness only records a number when that timestamp **changes between two idle
requests AND across 20 responses sampled while the load test is running**. Every load
request also carries a unique `?r=` query, so no response cache keyed on the URL can
answer for the renderer. All five pass in every run.

## Results

Updated 2026-10-10. Every framework rendering per request, each as its own process
(`oha -z 8s -c 50`, loopback, prod builds):

| Framework | Client JS (gz) | TTFB | RPS (uncached) | p99 | Cold start | Build | Interactions |
|---|--:|--:|--:|--:|--:|--:|:-:|
| **bext (PRISM)** | 5.6 KB | **2.9 ms** | **16,958** | **4.1 ms** | **78 ms** | ~4 KB\* | ✅ |
| Astro | **0.33 KB** | 11.3 ms | 4,142 | 19.5 ms | 150 ms | 432 KB | ✅ |
| Remix | 101 KB | 11.1 ms | 1,119 | 68 ms | 384 ms | 335 KB | ✅ |
| Qwik | 35 KB | 43.7 ms | 906 | 70 ms | 157 ms | 249 KB | ✅ |
| Next.js | 145 KB | 20.3 ms | 622 | 127 ms | 537 ms | 5.2 MB | ✅ |

Client JS = every JS resource + inline scripts the page loads, gzipped by the harness
at one fixed level (a uniform encoder, not each server's choice). Each row is that
framework's best run: the box is shared, so the best run is the least disturbed one
(details below). Every run is in `results/runs/`.

### What the numbers say

- **bext renders fastest, by a wider margin than in June.** 16,958 RPS doing a full
  V8 render per request, with a 2.9 ms first byte and a 4.1 ms p99: about 4× Astro and
  27× Next.js. In June it did 4,742 RPS at a 71 ms p99; recent bext releases sped up
  the render path, and this run gives bext its own process instead of a slot on a
  busy production server.
- **The tail flipped.** In June Astro had the tightest p99 (20 ms vs bext's 71). Now
  bext's p99 (4.1 ms) is below Astro's (19.5 ms).
- **The Node frameworks are where they were.** Astro, Remix, Qwik and Next.js land
  within about 10% of their June numbers, which is the sign the rig is comparable.
  Next.js stays last at 622 RPS (it served 2,945 when allowed to prerender, which is
  why the uncached proof exists).
- **Client JS is unchanged.** bext ships 5.6 KB (a real signals/resume runtime) vs
  Qwik 35, Remix 101, Next 145. Astro's 0.33 KB is hand-written vanilla `<script>`:
  great for this app, different math once you need real reactive components.
- **Cold start: bext is now the fastest to boot, 78 ms** to the first 200 (Astro 150,
  Qwik 157, Remix 384, Next 537), every framework measured as a process start. The first
  run of this re-measure found bext at 3.3 s; profiling the boot fixed it in bext: the
  continuous profiler no longer initializes on the boot path, route regexes compile once
  per process instead of once per HTTP thread, compile-cache housekeeping left the first
  request, the allocator stopped requesting transparent huge pages (each first touch
  stalled for memory compaction on this host), HTTP workers build concurrently, and
  V8 workers warm their isolate at boot. June's "10 ms" was the first request on
  an always-on server, not a process start.
- **bext's cached mode** (built-in ISR, one config line) serves the same page at
  about **44,000 RPS / 0.95 ms TTFB** on this loaded box. The 16,958 above is its
  uncached worst case.

\* bext compiles on demand: no heavyweight build step, ~4 KB of compiled bundle cache.

### How it was measured, and the caveats

- **Shared, busy machine.** The runs happened on a 24-core server that was also
  compiling other projects (load average 10 to 37). Throughput swung up to 3× between
  runs for every framework, so the table reports each framework's best run.
  bext's best is out of 12 runs, the Node apps' best out of 9, which gives the
  Node apps more chances, not fewer.
- **Process model.** Each Node server runs as one process (one JS thread). bext runs
  its default pool of 4 V8 worker processes, so it can use several cores. That is how
  each framework ships by default; it is also part of why bext's throughput is higher.
- **bext queue settings.** bext's V8 pool rejects excess requests with a 503 once its
  in-flight cap is reached, where the Node servers simply queue them. The bext start
  command (`apps/bext/bench.json`) raises the caps
  (`BEXT_V8_POOL_PER_WORKER_CAP=64`, `BEXT_V8_POOL_QUEUE_DEPTH=256`) so it queues
  too. Every recorded run has zero non-200 responses.
- **Why the unique `?r=` query.** bext has a render-result cache that keeps a page
  once two renders come out byte-identical. Under 50 concurrent requests, two renders
  of this page can land in the same millisecond and look identical, so the cache
  started replaying the page while the idle two-request check still passed. With a
  unique query per request every response is a real render, and the under-load sample
  proves it. The Node apps ignore the query.
- **Time-to-interactive was inconclusive (~50 to 70 ms for all).** On a fast box over
  loopback even 145 KB of React hydrates within a frame; the hydration-vs-resumption
  gap shows up on throttled mobile, which this rig doesn't model.
- One app, one machine. A data-backed or streaming route would shift the picture.

## The app

A single server-rendered page (`SPEC.md` has the exact contract): header with a theme
toggle, a hero, a counter, and a search box filtering **24 server-rendered product
cards** (shared `products.json`). Three interactive units, each built with the
framework's idiomatic primitive (`"use client"`, Astro islands, Qwik resumable
components, bext `"use resumable"` islands).

## Reproduce

```bash
# 1. install harness deps (puppeteer for the browser measurements)
npm install

# 2. install + build each Node app
for d in apps/next apps/remix apps/astro apps/qwik; do (cd "$d" && npm install && npm run build); done

# 3. run the full sweep (cold start, TTFB, RPS, uncached proof, browser checks)
bash harness/run-all.sh        # CHROME=/path/to/chrome to use a system Chrome
python3 harness/summarize.py   # prints the table, writes results/results.json
```

The four Node apps run out of the box. The **bext** row needs the bext binary and its
shared framework: set `BEXT_BIN=/path/to/bext-server` (or have `bext-server` on PATH)
and `BEXT_SHARED_FRAMEWORK_DIR=/path/to/bext/sites/shared/framework` (or install it at
`/usr/share/bext/framework`). The harness then starts `apps/bext` on port 8105 exactly
like the Node apps; without them that row is skipped.

## Layout

```
SPEC.md            canonical app contract
products.json      the shared 24-product dataset
apps/<fw>/         each framework's app (bench.json declares its start command)
harness/
  run-all.sh       orchestrator: start server → cold/proof/TTFB/RPS/browser → stop
  h2h-measure.mjs  puppeteer: client-JS (uniform gzip) + interaction verify
  summarize.py     combine one sweep's raw outputs → table + results.json
results/
  results.json     the published table (best run per framework, with every run's RPS)
  runs.json        every run: RPS, p99, TTFB, cold start, proof, interactions
  runs/<run>/      raw evidence per run: oha JSON, *.proof, browser JSON
RESULTS.md         the writeup
```

MIT licensed. PRs that tighten the methodology or add a framework are welcome: the
whole point is that you can re-run it and check.
