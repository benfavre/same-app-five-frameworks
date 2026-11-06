| Runtime | V8 / HTTP | Connections | Median RPS | RPS min–max | Server CPU equivalents | p99 |
|---|---|---:|---:|---:|---:|---:|
| Original immediate admission | 12 / 12 | 50 | 36,862 | 30,829–38,401 | 14.34 | 2.88 ms |
| Bounded admission wait | 12 / 12 | 50 | 36,652 | 35,303–36,764 | 14.12 | 3.05 ms |
| Bounded admission wait | 16 / 24 | 200 | 25,969 | 24,990–27,563 | 11.51 | 11.82 ms |
