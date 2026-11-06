All 24 logical CPUs available to the entire server tree and the co-located clients.

| V8 / HTTP workers | Connections | RPS median | RPS min–max | Server CPU equivalents | CPU ms/request | p99 |
|---|---:|---:|---:|---:|---:|---:|
| 4 / 1 | 50 | 10,969 | 10,928–11,122 | 2.77 | 0.2684 | 7.15 ms |
| 12 / 12 | 50 | 36,118 | 35,538–37,254 | 14.02 | 0.4128 | 3.23 ms |
| 16 / 24 | 50 | 34,734 | 34,217–38,144 | 14.59 | 0.4436 | 3.56 ms |
