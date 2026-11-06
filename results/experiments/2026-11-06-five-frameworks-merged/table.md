Server CPU affinity: `10` (1 logical CPU(s) for the entire server process tree).

| Framework | Client JS (KiB gz) | TTFB p50 (ms) | RPS median | RPS min–max | p99 (ms) | Process start (ms) | Output (KiB) | C/T/S |
|---|---:|---:|---:|---:|---:|---:|---:|:---:|
| Astro | 0.33 | 10.31 | 3,993 | 3,853–4,275 | 41.02 | 168 | 478.9 | ✓ |
| bext (PRISM) | 5.71 | 13.81 | 3,530 | 3,407–3,541 | 30.31 | 97 | 405.8 | ✓ |
| Qwik | 34.79 | 88.51 | 442 | 437–442 | 171.34 | 180 | 251.3 | ✓ |
| Next.js | 134.55 | 28.94 | 428 | 418–451 | 182.06 | 383 | 5,049.4 | ✓ |
| React Router (Remix) | 113.19 | 35.95 | 367 | 361–391 | 197.46 | 202 | 378.7 | ✓ |
