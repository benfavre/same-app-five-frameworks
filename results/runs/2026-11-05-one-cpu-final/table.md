Server CPU affinity: `10` (1 logical CPU(s) for the entire server process tree).

| Framework | Client JS (KiB gz) | TTFB p50 (ms) | RPS median | RPS min–max | p99 (ms) | Process start (ms) | Output (KiB) | C/T/S |
|---|---:|---:|---:|---:|---:|---:|---:|:---:|
| Astro | 0.33 | 9.93 | 4,290 | 4,169–4,336 | 36.89 | 168 | 478.9 | ✓ |
| bext (PRISM) | 5.71 | 22.94 | 2,102 | 2,079–2,175 | 65.00 | 104 | 405.8 | ✓ |
| Next.js | 134.55 | 28.63 | 448 | 441–453 | 170.24 | 396 | 5,049.4 | ✓ |
| Qwik | 34.79 | 95.86 | 415 | 365–417 | 187.43 | 184 | 251.3 | ✓ |
| React Router (Remix) | 113.19 | 39.72 | 369 | 365–378 | 190.14 | 222 | 378.7 | ✓ |
