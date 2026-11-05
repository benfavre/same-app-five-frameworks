Server CPU affinity: `10` (1 logical CPU(s) for the entire server process tree).

| Framework | Client JS (KiB gz) | TTFB p50 (ms) | RPS median | RPS min–max | p99 (ms) | Process start (ms) | Output (KiB) | C/T/S |
|---|---:|---:|---:|---:|---:|---:|---:|:---:|
| Astro | 0.33 | 10.07 | 4,252 | 4,179–4,299 | 37.58 | 174 | 478.9 | ✓ |
| bext (PRISM) | 5.71 | 14.04 | 3,469 | 3,448–3,477 | 31.78 | 96 | 405.8 | ✓ |
| Next.js | 134.55 | 28.54 | 443 | 441–452 | 181.36 | 389 | 5,049.4 | ✓ |
| Qwik | 34.79 | 95.08 | 401 | 394–430 | 187.89 | 180 | 251.3 | ✓ |
| React Router (Remix) | 113.19 | 40.51 | 359 | 355–364 | 199.21 | 206 | 378.7 | ✓ |
