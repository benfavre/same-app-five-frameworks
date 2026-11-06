Server CPU affinity: `10` (1 logical CPU(s) for the entire server process tree).

| Framework | Client JS (KiB gz) | TTFB p50 (ms) | RPS median | RPS min–max | p99 (ms) | Process start (ms) | Output (KiB) | C/T/S |
|---|---:|---:|---:|---:|---:|---:|---:|:---:|
| Astro | 0.33 | 8.77 | 4,975 | 4,665–5,165 | 29.13 | 169 | 478.9 | ✓ |
| bext (PRISM) | 5.71 | 12.27 | 3,732 | 3,370–3,844 | 31.45 | 98 | 405.8 | ✓ |
| Next.js | 134.55 | 26.72 | 482 | 478–507 | 165.01 | 425 | 5,049.4 | ✓ |
| Qwik | 34.79 | 81.11 | 471 | 468–486 | 164.32 | 178 | 251.3 | ✓ |
| React Router (Remix) | 113.19 | 36.99 | 368 | 360–379 | 203.17 | 205 | 378.7 | ✓ |
