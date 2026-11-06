| Runtime | Median RPS | RPS min–max | CPU ms/request | p99 |
|---|---:|---:|---:|---:|
| Same candidate, flag off | 3,735 | 3,440–3,738 | 0.2679 | 31.23 ms |
| Same candidate, flag on | 3,837 | 3,790–3,884 | 0.2604 | 30.01 ms |
| Astro, fresh matched comparison | 4,648 | 4,450–4,696 | 0.2147 | 31.37 ms |
| Bext, fresh matched comparison | 3,704 | 3,674–3,947 | 0.2695 | 33.25 ms |

| Compiler Request plan | V8 / HTTP | Connections | Median RPS | RPS min–max | Server CPU equivalents | p99 |
|---|---|---:|---:|---:|---:|---:|
| Off | 12 / 12 | 50 | 30,980 | 29,767–31,962 | 12.02 | 4.56 ms |
| On | 12 / 12 | 50 | 37,131 | 33,758–38,979 | 13.98 | 3.04 ms |
| On | 16 / 24 | 200 | 26,018 | 22,764–26,278 | 11.11 | 13.05 ms |
