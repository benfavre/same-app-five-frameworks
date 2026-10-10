# Head-to-head: bext vs Next.js / Remix / Astro / Qwik, UNCACHED

Same app ("Widget Showcase", see SPEC.md) built idiomatically on each framework:
SSR header + hero + 24 server-rendered product cards + three interactive units
(counter, theme toggle, client-side search). All five verified working in a real
headless browser (**C/T/S** = Counter / Theme / Search) in every run.

**Fairness:** every framework renders **fresh on every request**: no ISR cache
(bext `force-dynamic`), no prerendered static (Next.js `force-dynamic`, Astro
`prerender=false`). Proven per app and per run by a server-rendered `data-rendered-at`
timestamp that must differ between two idle requests **and** across 20 responses
sampled during the load test. Each load request carries a unique `?r=` query so no
URL-keyed response cache can stand in for the renderer.

Measured 2026-10-10 on activ-2 (24 cores, node 25, prod builds, loopback), each
framework as its own process. Client JS = every JS resource + inline scripts the page
loads, gzipped by us at one fixed level. TTFB / RPS / p99 from `oha -z 8s -c 50`.
Best run per framework (box shared with other workloads, see below).

| Framework        | Client JS (gz) | TTFB (p50) | RPS (uncached) | p99      | Cold start | Build  | C/T/S |
|------------------|---------------:|-----------:|---------------:|---------:|-----------:|-------:|:---:|
| **bext (PRISM)** | 5.58 KB        | **2.9 ms** | **16,958**     | **4.1 ms** | **78 ms**  | ~4 KB* | ✅ |
| Astro            | **0.33 KB**    | 11.3 ms    | 4,142          | 19.5 ms  | 150 ms     | 432 KB | ✅ |
| Remix            | 101.3 KB       | 11.1 ms    | 1,119          | 67.9 ms  | 384 ms     | 335 KB | ✅ |
| Qwik             | 34.9 KB        | 43.7 ms    | 906            | 70.4 ms  | 157 ms     | 249 KB | ✅ |
| Next.js          | 144.8 KB       | 20.3 ms    | 622            | 127.0 ms | 537 ms     | 5.2 MB | ✅ |

Every run (`results/runs.json`), RPS sorted:

| Framework | Runs | RPS per run |
|---|--:|---|
| bext    | 12 | 5,750 · 6,049 · 6,535 · 6,750 · 9,914 · 10,497 · 10,823 · 11,878 · 12,476 · 14,718 · 15,173 · 16,958 |
| Astro   | 9 | 1,673 · 1,809 · 1,813 · 1,871 · 3,592 · 3,935 · 4,025 · 4,030 · 4,142 |
| Remix   | 9 | 322 · 342 · 371 · 372 · 854 · 1,053 · 1,073 · 1,100 · 1,119 |
| Qwik    | 9 | 348 · 350 · 351 · 382 · 569 · 880 · 888 · 905 · 906 |
| Next.js | 9 | 215 · 217 · 220 · 244 · 281 · 339 · 583 · 588 · 622 |

The low runs coincide with heavy compile jobs from another project on the same box
(load average up to 37 on 24 cores). Each framework's best run is its least disturbed
one; the Node apps had 9 chances, bext 12 (the last 9 on releases with the
cold-start fixes below).

## What the uncached numbers say

**bext is the fastest renderer, by a wider margin than in June.** A full V8 render per
request at **16,958 RPS**, **2.9 ms** first byte and **4.1 ms** p99: about 4× Astro,
15× Remix, 19× Qwik, 27× Next.js. June measured 4,742 RPS at a 71 ms p99.

**The tail flipped.** Astro had the tightest p99 in June (20 ms vs 71). bext's is now
4.1 ms against Astro's 19.5.

**The Node frameworks barely moved** (within about 10% of June), so the rig is
comparable and the change is bext's.

**Client JS is unchanged: kilobytes, not megabytes.** bext ships 5.6 KB (3 resumable
islands + shared runtime); Astro wins outright at 0.33 KB of hand-written vanilla
`<script>`, Qwik 35, Remix 101, Next 145.

**Cold start: 78 ms, now the fastest of the five** (Astro 150, Qwik 157, Remix 384,
Next 537). The first runs of this re-measure showed ~3.3 s. Profiling bext's boot
found six causes, all fixed and deployed in bext:

| Fix | Cold start after |
|---|--:|
| (start of re-run) | 2.4 to 5 s |
| continuous profiler starts 10 s after boot instead of before listening | ~160 to 300 ms |
| actix route regexes compiled once per process, not once per HTTP thread | |
| disk compile-cache prune moved off the first request | ~100 to 300 ms |
| allocator stops requesting transparent huge pages (compaction stalls) | ~110 ms, steady |
| actix HTTP workers build their apps concurrently (were built one after another) | |
| V8 workers create their isolate and a warm context at boot, not on the first request | **~75 ms** |

**Cached mode.** With its built-in ISR (one config line) bext serves the same page at
~44,000 RPS / 0.95 ms TTFB / ~4 ms p99 standalone on this loaded box. (June's 282,776
RPS was measured on the fleet front server on a quiet box, a different setup.)

**TTI inconclusive (~50 to 70 ms for all):** on a fast box over loopback even 145 KB of
React hydrates within a frame. The hydration-vs-resumption gap needs throttled mobile.

\* bext has no heavyweight build (compiles on demand; ~4 KB bundle cache).

## What changed since the June run

- **bext runs as its own process** (`apps/bext/bench.json`, started and stopped by the
  harness like the Node apps) instead of on the shared production front server. Its
  default 4-worker V8 pool is kept; the admission caps are raised so it queues excess
  requests like the Node servers instead of answering 503. Zero non-200s in every run.
- **Unique query per load request + under-load proof.** bext's render-result cache can
  keep a page after two byte-identical renders; at 50 concurrent requests two renders
  of this page can share a millisecond, look identical, and get replayed. The June
  idle check could not see that. The harness now samples during load and every load
  request is unique.
- **Cold start is now spawn-to-first-200 for everyone**, bext included (June's 10 ms
  was the first request on an always-on server).
- **Harness fixes:** `run_node` resolved the app directory from the previous loop
  iteration's variable (harmless inside the loop, wrong outside it); the proof files
  are now valid JSON.
- **bext cold start fixed during the re-run** (six boot-path fixes, see above); the
  bext row's cold start comes from the fixed release.
- **bext's islands were broken in production** when this re-run started: the shared
  resume runtime shipped as raw ESM, so all three interactions failed. Fixed in bext
  (`fix(turbopack): inline type import specifiers no longer ship the entry as raw ESM`)
  and deployed before these runs.

## Reproduce
- `harness/run-all.sh`: full sweep (cold start, uncached proof, TTFB, oha, browser)
- `harness/h2h-measure.mjs`: per-page client JS + interaction verify
- `harness/summarize.py`: one sweep's table + `results/results.json`
- `results/runs/<run>/`: raw oha JSON, `*.proof` (uncached evidence), browser JSON
