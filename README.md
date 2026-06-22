# Same App, Five Frameworks — an honest, uncached SSR benchmark

One identical app, built idiomatically in **Next.js, Remix, Astro, Qwik, and
[bext](https://bext.dev)**, with every framework forced to **render fresh on
every request** — no caching, no prerendering — and the fairness **proven in the
output**. Measured: client JS shipped, TTFB, requests/sec, p99, cold start, build
size, and whether the three interactions actually work in a real browser.

Most framework benchmarks quietly compare a cached/prerendered response against an
uncached one. This one doesn't: each app renders a `data-rendered-at` timestamp and
the harness **requires it to change between two back-to-back requests** before it
records a number. All five verified `uncached = true`.

## Results

Every framework rendering per request (`oha -z 8s -c 50`, loopback, prod builds):

| Framework | Client JS (gz) | TTFB | RPS (uncached) | p99 | Cold start | Build | Interactions |
|---|--:|--:|--:|--:|--:|--:|:-:|
| **bext (PRISM)** | 5.6 KB | **6.0 ms** | **4,742** | 71 ms | 10 ms\* | ~4 KB\* | ✅ |
| Astro | **0.33 KB** | 12.3 ms | 3,807 | **20 ms** | 155 ms | 432 KB | ✅ |
| Remix | 101 KB | 12.2 ms | 1,011 | 75 ms | 362 ms | 335 KB | ✅ |
| Qwik | 35 KB | 42.6 ms | 938 | 73 ms | 160 ms | 249 KB | ✅ |
| Next.js | 145 KB | 21.1 ms | 575 | 141 ms | 510 ms | 5.2 MB | ✅ |

Client JS = every JS resource + inline scripts the page loads, gzipped by the harness
at one fixed level (a uniform encoder, not each server's choice).

### What the numbers say

- **bext renders fastest** doing a full render per request: 4,742 RPS, 6 ms first byte.
- **The fairness rule cost Next.js the most.** Cached/prerendered it served 2,945 RPS;
  forced to actually SSR per request it dropped to **575 — a 5× fall.** It had been
  handing back prerendered static HTML. Remix/Astro/Qwik barely moved (already
  per-request), which is exactly why the proof step exists.
- **Astro is the genuine rival** — 3,807 RPS and the tightest tail (p99 20 ms) because
  it ships essentially no runtime. Its 0.33 KB is hand-written vanilla `<script>`; great
  for this app, different math once you need real reactive components.
- **Client JS is unchanged by caching.** bext ships 5.6 KB (real signals/resume runtime,
  ~0.8 KB lazy) vs Qwik 35, Remix 101, Next 145.
- **bext's cached mode** (built-in ISR, one config line) serves the same route at
  **282,776 RPS / 0.13 ms TTFB** — the 4,742 above is its worst case.

\* bext compiles on demand (no heavyweight build; ~4 KB bundle cache) and has no
process-boot cold start (its runtime is always warm — the 10 ms is first compile +
render). Next's 5.2 MB `.next` and 510 ms boot are the outliers.

### Honest caveats

- **Time-to-interactive was inconclusive (~51–55 ms for all).** On a fast box over
  loopback even 145 KB of React hydrates within a frame; the hydration-vs-resumption
  gap shows up on throttled mobile, which this rig doesn't model. JS size and RPS/TTFB
  are the discriminating columns here.
- One app, one machine. A data-backed or streaming route would shift the picture.
- Raw evidence (per-app `oha` JSON + the uncached `*.proof` timestamps) is in `results/`.

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

# 2. install + build each app
for d in apps/next apps/remix apps/astro apps/qwik; do (cd "$d" && npm install && npm run build); done

# 3. run the full sweep (cold start, TTFB, RPS, browser client-JS + interaction checks)
bash harness/run-all.sh        # CHROME=/path/to/chrome to use a system Chrome
python3 harness/summarize.py   # prints the table, writes results/results.json
```

The four Node apps run out of the box. The **bext** entry needs the bext runtime serving
the app (`apps/bext/` is the source); point the harness at it with
`BEXT_URL=http://your-bext-host/ bash harness/run-all.sh`, otherwise that row is skipped.

## Layout

```
SPEC.md            canonical app contract
products.json      the shared 24-product dataset
apps/<fw>/         each framework's app (bench.json declares its start command)
harness/
  run-all.sh       orchestrator: start server → cold/TTFB/RPS/browser → stop
  h2h-measure.mjs  puppeteer: client-JS (uniform gzip) + interaction verify
  summarize.py     combine raw outputs → table + results.json
results/           results.json + per-app oha JSON + *.proof (uncached evidence)
RESULTS.md         the writeup
```

MIT licensed. PRs that tighten the methodology or add a framework are welcome — the
whole point is that you can re-run it and check.
