# Same App, Five Frameworks

One small app in Next.js, React Router (the Remix entry), Astro, Qwik, and bext:
24 server-rendered product cards, a counter, a persisted theme toggle, and live
client-side search. Every measured request renders fresh HTML.

## Current results — 2026-11-05

| Framework | Version | Client JS (KiB gz) | RPS median | TTFB p50 (ms) | p99 (ms) |
|---|---|---:|---:|---:|---:|
| bext (PRISM) | 0.2.9* | 5.71 | 15,874 | 3.10 | 4.70 |
| Astro | 7.4.6 | 0.33 | 5,446 | 8.68 | 14.02 |
| Qwik | 1.20.3 | 34.79 | 1,176 | 34.41 | 75.28 |
| React Router (Remix) | 8.5.1 | 113.19 | 1,076 | 12.86 | 59.22 |
| Next.js | 16.4.5 | 134.55 | 687 | 17.43 | 97.08 |

*The local bext runtime and toolkit are identified by exact SHA-256 hashes in the [run metadata](results/runs/2026-11-05/metadata.json).

Three equal sweeps per framework on activ-2 (AMD Ryzen 9 5900X, 12 cores / 24
threads), production servers over loopback. Node v26.12.1, oha 1.14.0, Puppeteer
25.16.0 and Chrome 152.0.7977.75. RPS, TTFB and p99 are medians across the three
sweeps; [the full ranges and every run](RESULTS.md) are retained. These are
observations on a shared host.

[RESULTS.md](RESULTS.md) explains the versions, raw evidence, startup and size
measurements, and limits of comparisons with the older results.

## What is checked

- Uncached SSR: two different idle timestamps plus 20 different timestamps sampled
  during the actual load test. oha samples a pool of one million distinct query
  URLs with replacement; bext's render-result cache is explicitly disabled.
- All 24 card elements and product names exist in the raw server HTML.
- A real browser increments the counter, toggles and persists the theme across a
  reload, filters the expected cards with mixed-case input, and restores all cards
  when the input is cleared.
- Every measured load response is HTTP 200, with no transport errors. Missing or
  failed evidence fails the campaign and prevents publication.

## Reproduce

Requires Node >=22.23.4, npm, Python 3, oha, and Chrome (Puppeteer downloads a
compatible browser during installation; `CHROME=/path/to/chrome` overrides it).

```bash
npm ci
for fw in next remix astro qwik; do
  (cd "apps/$fw" && npm ci && npm run build) || exit 1
done

# bext runs as a separate production server, with an external runtime/toolkit:
export BEXT_BIN=/absolute/path/to/bext-server
export BEXT_SHARED_FRAMEWORK_DIR=/absolute/path/to/bext/sites/shared/framework

npm run benchmark
npm run summarize -- --publish
```

The runner prints its new `results/runs/<campaign>/` directory. To summarize an
explicit campaign: `npm run summarize -- results/runs/<campaign> --publish`.
The summary refuses incomplete or failed campaigns. `--publish` updates the local
`results/results.json` and `results/latest.json`; it does not push to GitHub.

To measure only the four Node apps, choose them explicitly:

```bash
npm run benchmark -- --frameworks next remix astro qwik
```

Defaults: three sweeps, three process starts per entry per sweep, two-second
warmup, then `oha -z 8s -c 50 -w` with HTTP/1.1 keep-alive. The framework order
rotates across sweeps. Override `--repeats`, `--duration`, `--concurrency`,
`--cold-samples`, or `--output` as needed. Output directories must be new. Occupied
ports are an error; the runner only stops the process groups it starts.
`bash harness/run-all.sh` is the equivalent compatibility entrypoint.

## Measurements and limits

Client JS uses one uniform gzip encoder (level 6) for each external JS resource
plus concatenated inline script bodies, including serialized data. It includes
code fetched during the three interactions; the initial-visit size is also saved.
KiB means 1,024 bytes. Astro implements the interactions with a small vanilla DOM
script, while the other entries ship their respective reactive/resume runtimes.

TTFB is p50 under concurrency 50, not idle navigation latency. Process start is
spawn-to-first-complete-200 with warm filesystem/compilation caches, without `npx`
launcher overhead. Output sizes exclude dependencies and server/runtime binaries;
bext's row describes generated runtime state, including local databases, which is
not equivalent to a Node build artifact. The bext server uses four V8
workers; each Node server uses its default single process. This compares the
configured servers, not equal per-core efficiency. No mobile throttling or
navigation-to-interactive result is claimed.

[The canonical contract](SPEC.md), [current evidence](results/runs/2026-11-05/),
and [October's historical writeup](results/history/2026-10-10.md) are included.
Harness integrity checks: `python3 -m unittest discover -s harness -p 'test_*.py'`.

MIT licensed.
