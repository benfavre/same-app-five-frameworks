# Steady comparison with 20-second warmup

All five frameworks use 20 seconds of warmup before the same eight-second, 50-connection load. Three sweeps rotate framework order; three process-start samples precede each entry. Every server process and thread shares CPU 10, and clients exclude CPUs 10 and 22. The host is shared; this is an affinity limit, not an exclusive reserved core.

Bext uses the accepted prepared/hash/scanner/compact-text/native-HTML settings, four V8 workers, one HTTP worker, default nursery/IPC, and warn-level detailed Rust tracing. HTTP access logging and continuous profiling remain enabled. Its compiled native/SDK inputs match the qualified merged source; the rejected reply writer/read buffer and pending direct-props prototype are excluded. Exact identities and overrides are in [metadata](metadata.json) and [qualification](qualification.json).

The continuous profiler starts its initial guard 10 seconds after server startup. A separate 30-second probe measured about 0.93 CPU-seconds of initialization between approximately 10 and 13.5 seconds; that overlapped the earlier two-second-warmup/eight-second-load window. The longer warmup passes that observed initialization. Other frameworks also benefit from warmup, so changes relative to earlier campaigns are not isolated Bext code speedups.

All 15 entries pass browser/SSR/freshness/HTTP/affinity checks. There were 238,454 measured HTTP 200 responses and zero load errors or affinity violations. The table retains all observed ranges; no confidence intervals or general tail-latency guarantee are inferred. Production is unchanged.

[Full table](table.md), [summary](summary.json), [earlier short-warmup campaign](../2026-11-06-five-frameworks-merged/notes.md). The default baseline pointer remains unchanged; `results/latest-tuned.json` points here.
