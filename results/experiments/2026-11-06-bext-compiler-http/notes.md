# Whole-HTTP profiling and compiler Request plans

This experiment tests whether removing repeated route setup can close the
one-CPU gap to Astro. It keeps fresh rendering, continuous profiling and HTTP
access logging enabled. Render-result caching is disabled. Production binaries
and services are unchanged.

## Fresh baseline

Three alternating Astro/Bext sweeps use 20-second warmups, 15-second loads,
50 connections, and one process start per entry. Every server process/thread
shares CPU 10. Clients exclude CPU 10 and its SMT sibling 22. This is a shared
host, not an exclusive CPU reservation.

| Framework | Median RPS | RPS min–max | p99 |
|---|---:|---:|---:|
| Astro | 4,863 | 4,561–4,994 | 28.84 ms |
| Bext, merged admission wait | 3,726 | 3,695–3,852 | 30.96 ms |

All six warmup/load/browser/SSR/freshness/affinity entries pass. The baseline
uses native SHA-256 `33fdc09dc6fd8090c99efeffbd2b9e08443c50d8e6429f1e118e04320b423af7`
and frozen SDK manifest `ae92033bc02dc15d6586a2f88b81092b3829ccc8e3478ea2e03ad4a0e130762e`.
See [raw baseline](baseline/) and [summary](baseline/summary.json).

## HTTP profile

A separate 12-second diagnostic samples the controller and all four V8 worker
processes after the same warmup. It is a whole-HTTP profile, distinct from the
earlier renderer-only profile. The controller consumes 6.15 CPU seconds and
workers 5.88 CPU seconds: approximately half the server CPU in each role.
`std::fs::metadata` accounts for about 7.9% of inclusive sampled CPU. Copying,
allocation, V8 string flattening and syscalls also appear. Unresolved JavaScript
stacks prevent attributing exact percentages to JavaScript operations.

The profile motivates testing repeated setup; it does not establish that
string copies alone explain the HTTP throughput gap. Diagnostic throughput is
excluded from the comparison. [CPU roles](http-profile/cpu.json),
[flat samples](http-profile/flat.txt), [inclusive samples](http-profile/inclusive.txt),
[profile provenance](http-profile/qualification.json). Display reports abbreviate
long symbols; full reports and raw perf data remain locally retained with hashes.

## Prototypes

The compiler Request-plan prototype is opt-in with `BEXT_PRISM_CALL_PLANS=1`.
It registers facts about original hoisted function identities in a WeakMap.
Parameterless functions that cannot inspect their arguments can omit their
Request. Layout functions reading only guaranteed `children`/`route` props can
omit the layout Request. Request readers, escaping or reflected arguments,
unknown syntax/scopes, reassigned function identities, invalid URLs and unusual
methods retain the ordinary path. Layout-only facts cannot be used for loaders.
The existing JSX string-folding compiler remains in place.

The [native HTTP activation fixture](activation.json) verifies two Request
constructions per render with the flag off and zero with it on, with both
actual adapter functions registered. It uses disposable fixture copies only.
[Eighteen source/API invalidation cases](call-plan-source-invalidation.json)
pass, including fresh GET/POST inputs and page/layout/import changes.

The separate bootstrap prototype reuses one normalized immutable compiler
script. It retains at most one input/output string pair, switches immediately
for a different bootstrap and never caches response HTML or loader results.
Its regression exercises fresh renders, alternating script inputs and listener
disposal when the cached script is replayed in a browser-like environment.

Initial screen and rebuild/SDK controls are retained in [screen.json](screen.json)
and [isolate.json](isolate.json). They are preliminary points, not headline
improvement claims. Independent confirmation rotates original, compiler-plan
and bootstrap-only arms in ABC/BCA/CAB order, with three fresh-server entries
per arm. Every entry repeats the full warmup/load/browser/freshness/CPU contract.
See [confirmation](confirmation.json).

The initial compiler source is `011323800518c2ed1782f25df4c0af8b3dde0880`; native SHA-256
is `aa3e016bcce6c6edc1a498897c62ec1c4403bd37c3eeb73376c7b6628cae56f8`.
The canonical 18-feature PHP-ZTS release build passes. Seventy compiler tests
pass, with two existing ignored cases; 109 SDK tests pass. Bootstrap-only tests
pass 101/101. [Builds, tests, guarded attempts and identities](build-and-tests.json)
retain setup failures and corrections rather than counting them as passes.
The SDK test selection runs through the pinned `bun-test` wrapper; no external
TypeScript checker pass is claimed.

Accepted preparation/hash/scanner/text flags, wait 250 ms, four V8 workers and
one HTTP worker apply to every Bext entry. Each metadata file records exact
binary/SDK/source identities and flags. Heavy work is serialized by the existing
measurement lock, with a 10 GiB owned-tree RSS cap, 8 GiB host-memory and 4 GiB
disk headroom. Native stages have 40-minute deadlines; benchmark phases have
20-minute deadlines. Task-owned server logs are losslessly compressed locally
with original/compressed hashes; raw JSON, failed controls and reproduction
scripts are retained.

## Final artifact qualification

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

The final same-binary compiler flag comparison changes one-CPU median RPS +2.75% and CPU/request -2.78%. Full-machine 50-connection median RPS changes +19.86%. All 21 final entries pass: 6,313,401 warmup and 4,880,426 measured HTTP 200 responses, zero warmup/load errors. Three 200-connection entries pass without 503 responses. Astro remains ahead in the final matched one-CPU comparison.

Final source is `6724dee3790848b6bfb5166d1aa81e01094210d4`, native SHA-256 `72f972a6e9262c22af7e1a5bdd2b19f73d09b09825723505de51e8a347a6e489`. [The cache-fingerprint proof](emitter-fingerprint-proof.json), final native HTTP activation and all 18 source/API invalidation cases pass. The initial binary remains at its separately recorded retained path. Initial and final artifacts are never pooled for headline medians. [Strict publication recheck and complete phase data](qualification.json).

## Reproduce the matched comparison

Build the recorded Bext source with the canonical 18-feature PHP-ZTS command
in its repository instructions, and use its matching framework SDK. Set
`BEXT_BIN` and `BEXT_SHARED_FRAMEWORK_DIR` to those private artifacts. On activ-2:

```bash
npm run benchmark -- --frameworks astro bext --repeats 3 --cold-samples 1 \
  --server-cpus 10 --client-cpus 0-9,11-21,23 \
  --warmup-seconds 20 --duration 15 --concurrency 50 \
  --bext-v8-workers 4 --bext-http-workers 1 --bext-log-filter warn \
  --bext-flag BEXT_PRISM_PREPARED_PAGES=1 \
  --bext-flag BEXT_V8_LEGACY_HASH_HINT=1 --bext-flag BEXT_V8_MULTIPLEX=0 \
  --bext-flag BEXT_PRISM_TOKEN_SCAN=1 --bext-flag BEXT_V8_PREPARED_TEXT=2 \
  --bext-flag BEXT_PRISM_NATIVE_HTML_SCAN=1 \
  --bext-flag BEXT_V8_SITE_WAIT_MS=250 --bext-flag BEXT_PRISM_CALL_PLANS=1 \
  --output results/runs/local-compiler-plans
```

Choose CPU IDs from the host topology elsewhere. For the flag comparison run
Bext alone, toggling only `BEXT_PRISM_CALL_PLANS`, in off/on, on/off, off/on order
with a fresh directory per cell. For the full-machine 50-connection comparison
use CPUs/clients `0-23` and 12 V8 / 12 HTTP workers. For the candidate 200-connection
row use 16 V8 / 24 HTTP workers and three repeats. Exact task drivers and options
are retained under [reproduction](reproduction/); their private artifact paths
must exist before use. Lossless raw server logs and perf data are retained at
the recorded local paths; JSON evidence and their hashes are versioned here.

The native implementation is merged in [Bext PR #432](https://github.com/benfavre/bext/pull/432) as `22b2524df8f065285bbd4f76b96efc4635ecdcb7`. Native/Cargo/SDK inputs match the qualified code commit exactly; the PR head adds documentation only. The production binary and service flags remain unchanged.
