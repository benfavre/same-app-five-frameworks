# Head-to-head benchmark — canonical app spec

One identical app, implemented idiomatically in each framework. The point is a
**fair** comparison: every framework renders the same SSR HTML and ships the same
three interactive behaviors. Differences in shipped JS / hydration cost are the
*model* differences (full hydration vs islands vs resumability), which is exactly
what we want to surface — not differences in the app.

## The app: "Widget Showcase" — a single page at `/`

Server-rendered page containing, in order:

1. **Header** — the framework name + a **theme toggle** button.
   - Toggle flips `<html>` between a light and dark class, and persists choice to
     `localStorage` (key `theme`). On load, respects the stored value.
2. **Hero** — an `<h1>` title and a `<p>` subtitle. Pure static SSR text.
3. **Counter** — a button labeled `Count: N` (starts 0). Click increments.
4. **Catalog** —
   - A **search `<input>`** (placeholder "Filter products…").
   - A grid of **24 product cards** rendered server-side from the shared
     `products.json` (name, price, category). Each card shows name, category, price.
   - Typing in the search filters the visible cards by name (case-insensitive,
     substring), live on every input event. Filtering is client-side.
5. **Footer** — static text "Built with <framework>".

### Rules for fairness
- The 24 products come from the shared `products.json` — same data in every app.
- SSR must emit all 24 cards in the initial HTML (no client-only rendering of the
  list). Verified by grepping the raw HTML for all 24 names.
- Use each framework's **idiomatic** interactivity primitive:
  - Next.js (App Router): server components + `"use client"` islands.
  - Remix: loader + client components (route hydrates).
  - Astro: static + `client:load` / `client:visible` islands (vanilla or React).
  - Qwik (QwikCity): resumable components, default.
  - bext (PRISM): `"use resumable"` islands.
- No analytics, no extra fonts, no images. Minimal CSS, inline or one small file.
- Production build + production server. No dev mode in any measurement.
- Each app's prod server binds to its assigned port (see ports.txt).
- Compare CPU budgets explicitly. One Node server process is not a guarantee of
  one CPU: GC/JIT helpers can run on other threads. For an equal-CPU headline,
  apply the same `--server-cpus` affinity mask to every server and descendant,
  and keep the load generator off that physical core and its SMT sibling.
  Unrestricted/default-worker results must be labeled as configured-server
  throughput, not per-core performance.
- Every request must render fresh. A positive server-rendered `data-rendered-at`
  timestamp must change between two idle requests and across 20 responses sampled
  during the measured load test. oha samples from one million distinct `?r=` URLs
  with replacement; individual request URLs can repeat. Framework response caches
  must be disabled explicitly, including bext's render-result cache.

## Metrics (collected centrally by the harness, identically for all)
- **build_bytes** — measured production output files (Qwik: `dist` + `server`;
  Next: `.next` excluding compiler `cache` and `diagnostics`; bext: its generated
  `.bext` directory, including local runtime databases and route wrappers).
  Excludes dependencies and framework/server executables. The bext state directory
  is not equivalent to a Node build artifact; none of these sizes is a total
  deployment footprint.
- **client_js_gz** — sum of each distinct external JS resource gzipped at level 6,
  plus concatenated inline script bodies (including serialized script data) gzipped
  at the same level. Count a fresh browser visit and the three interactions; stop
  counting before the persistence-check reload. Also record the initial-visit size.
- **cold_start_ms** — spawn production server → first complete HTTP 200 at `/`.
  Three fresh processes per sweep, with OS/filesystem and compilation caches left
  warm; report the median of all process starts. Poll at 5 ms intervals. Start
  commands invoke local Node entrypoints directly, without `npx` startup overhead.
- **ttfb_ms** — first-byte p50 during load, from `oha` (not an idle curl latency).
- **rps / p99** — `oha -z 8s -c 50 -w`, HTTP/1.1 keep-alive, varied query URLs, after a
  2-second warmup. Wait for in-flight requests at the deadline. Require only HTTP
  200 responses, successRate=1 and an empty error distribution.
- **interaction checks** — counter increments, theme toggles and persists after a
  reload (then toggles back), mixed-case search matches exactly the expected cards,
  and clearing the input restores all 24 cards. Verify all 24 names and card
  elements in the raw SSR HTML. The click latency after settling is diagnostic,
  not a navigation-to-interactive measurement.
- **CPU audit** — sample the server process tree every 250 ms during the load
  interval. Record process CPU ticks and every thread's affinity mask. Any escaped
  mask, missing CPU evidence, or audit error fails the campaign/summary. The audit
  window includes oha startup/URL-file parsing and final accounting; sampled CPU
  seconds and average occupied CPUs are diagnostics, not a precise profiler trace.
  CPU ms/request divides server-tree CPU time by the measured HTTP-200 count;
  the small amount of proof traffic and server background work is included.

Default campaign: three serialized sweeps of every framework, with order rotated
between sweeps. Report medians and the full RPS range; retain every run, without
selecting the best attempt. All sizes displayed as KiB (1,024 bytes).

Linux resource controls: `--server-cpus` and `--client-cpus` accept CPU IDs/ranges;
`--bext-v8-workers` and `--bext-http-workers` record explicit worker overrides.
`taskset` affinity is inherited by child processes and threads, then verified by
the audit. It does not reserve exclusive use of a physical core on a shared host.

## Output contract (each app dir must provide)
- `bench.json` at the app root:
  `{ "framework": "...", "port": N, "buildDir": "...", "start": "<cmd>" }`
  (use `buildDirs: ["dist", "server"]` when multiple directories are required).
- A working `start` command that serves the production build on `port`.
- Evidence is isolated in `results/runs/<campaign>/run-N/`. A failed/missing check
  fails the campaign and its summary; previous results cannot fill missing cells.
