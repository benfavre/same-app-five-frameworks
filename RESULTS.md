# Head-to-head: bext vs Next.js / Remix / Astro / Qwik — UNCACHED

Same app ("Widget Showcase" — see SPEC.md) built idiomatically on each framework:
SSR header + hero + 24 server-rendered product cards + three interactive units
(counter, theme toggle, client-side search). All five verified working in a real
headless browser (**C/T/S** = Counter / Theme / Search).

**Fairness fix:** every framework is forced to render **fresh on every request** —
no ISR cache (bext), no prerendered static (Next.js `force-dynamic`, Astro
`prerender=false`). Proven per app by a server-rendered `data-rendered-at`
timestamp that **differs on every request** (all four Node apps + bext verified
`uncached=true`). So these are pure render-and-serve numbers, apples-to-apples.

Measured on activ-2 (node 25, prod builds, prod servers, loopback). Client JS = every
JS resource + inline scripts the page loads, gzipped by us at one fixed level.
TTFB / RPS / p99 from `oha -z 8s -c 50`.

| Framework        | Client JS (gz) | TTFB (p50) | RPS (uncached) | p99      | Cold start | Build | Interactions |
|------------------|---------------:|-----------:|---------------:|---------:|-----------:|------:|:---:|
| **bext (PRISM)** | 5.59 KB        | **6.0 ms**  | **4,742**     | 71.0 ms  | 10 ms*     | ~4 KB* | ✅ |
| Astro            | **0.33 KB**    | 12.3 ms    | 3,807          | **20.5 ms** | 155 ms  | 432 KB | ✅ |
| Remix            | 101.3 KB       | 12.2 ms    | 1,011          | 75.1 ms  | 362 ms     | 335 KB | ✅ |
| Qwik             | 34.9 KB        | 42.6 ms    | 938            | 73.0 ms  | 160 ms     | 249 KB | ✅ |
| Next.js          | 144.8 KB       | 21.1 ms    | 575            | 141.2 ms | 510 ms     | 5.2 MB | ✅ |

## What the fair (uncached) numbers say

**bext is the fastest renderer — for real, not via cache.** Doing a full V8 render
on every request, bext sustains **4,742 RPS** with a **6 ms** first byte: the highest
throughput and lowest TTFB of the five. Astro is the only one close (3,807 RPS) and
actually has the tightest tail (p99 20 ms) because its per-request render is the
lightest — it ships no runtime, so there's little to do per request. bext pushes more
total throughput but with a longer tail (p99 71 ms). The React frameworks trail badly:
Remix/Qwik ~1,000 RPS, Next.js dead last at 575.

**The fairness fix mattered most for Next.js.** Cached/prerendered, Next served 2,945
RPS; forced to actually SSR per request it collapsed to **575 RPS (5× drop)** — it had
been serving prerendered static HTML, not rendering. Remix/Astro/Qwik barely moved
(they were already rendering per request), which is exactly why the proof step was
worth doing.

**Client JS is unchanged by caching — kilobytes, not megabytes.** bext ships 5.6 KB
(3 resumable islands + shared runtime; ~0.8 KB in lazy mode); ~18× less than Qwik,
~26× less than Next. Astro wins outright at 0.33 KB, but that's hand-written vanilla
`<script>` with no runtime — bext's 5.6 KB buys a real signals/resume runtime that
scales to genuine reactive components. bext sits with Astro/Qwik in the light camp and
laps the React frameworks.

**And bext keeps its trump card.** Uncached it's already the fastest; with its
**built-in ISR cache** (one config line, not an external CDN) the same route serves
**282,776 RPS at 0.13 ms TTFB / 0.64 ms p99**. That's the real-world deployment mode —
the uncached 4,742 is the worst case, and it still wins.

**TTI inconclusive (~51–55 ms for all)** — on a fast box over loopback even 145 KB of
React hydrates within a frame, so it doesn't discriminate here. The
hydration-vs-resumption gap shows up on throttled mobile, which this rig doesn't model.

\* bext has no heavyweight build (compiles on demand; ~4 KB bundle cache) and no
process-boot cold start (the Rust master is always warm — the 10 ms is first compile +
render). Next's 5.2 MB `.next` and 510 ms boot are the outliers.

## Reproduce
- `harness/run-all.sh` — full sweep (cold-start, TTFB, oha, browser, uncached proof)
- `harnesses/browser/h2h-measure.mjs` — per-page client-JS + interaction verify
- `harness/summarize.py` — table + `results/results.json`; per-app `*.proof` = uncached evidence
- bext at `http://h2h-bext.local/` (vhost `zz-h2h-bext-bench.conf`), page `export const dynamic = "force-dynamic"`
