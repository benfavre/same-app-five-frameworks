Server CPU affinity: `10` (1 logical CPU(s) for the entire server process tree).

| Framework | Client JS (KiB gz) | TTFB p50 (ms) | RPS median | RPS min–max | p99 (ms) | Process start (ms) | Output (KiB) | C/T/S |
|---|---:|---:|---:|---:|---:|---:|---:|:---:|
| Astro | 0.33 | 8.89 | 4,863 | 4,561–4,994 | 28.84 | 190 | 478.9 | ✓ |
| bext (PRISM) | 5.71 | 12.20 | 3,726 | 3,695–3,852 | 30.96 | 105 | 405.8 | ✓ |
