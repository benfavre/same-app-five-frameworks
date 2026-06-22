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

## Metrics (collected centrally by the harness, identically for all)
- **build_bytes** — size of the production build output dir.
- **client_js_gz** — sum of gzipped bytes of every `<script src>` the page loads
  (the bytes a real browser downloads to run the page). The headline number.
- **cold_start_ms** — spawn prod server → first HTTP 200 at `/`. Median of 3.
- **ttfb_ms** — warm, median of 50 sequential `/` requests.
- **rps / p99** — `oha -z 10s -c 50` against `/`.
- **hydrate_ms** — puppeteer: navigation → counter click registers (interactive).

## Output contract (each app dir must provide)
- `bench.json` at the app root:
  `{ "framework": "...", "port": N, "buildDir": "...", "start": "<cmd>", "buildBytes": N }`
- A working `start` command that serves the production build on `port`.
