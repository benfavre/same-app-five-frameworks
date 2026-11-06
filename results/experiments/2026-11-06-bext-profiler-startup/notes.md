# Delayed profiler startup probe

A 30-second load with the existing two-second warmup samples the owned controller's thread CPU ticks and all process/thread affinity masks. The profiler rollover thread accumulates **0.93 CPU-seconds between approximately 10.12 and 13.54 seconds after startup**. Access-log buckets show throughput dipping during the initialization period and recovering afterward. This overlaps the tail of the earlier two-second-warmup/eight-second-load method.

This diagnostic does not isolate all ongoing sampling overhead and is not a full framework benchmark. Access buckets include warmup plus load and have one-second wall-clock boundaries. The [20-second-warmup full comparison](../2026-11-06-five-frameworks-steady/notes.md) applies the same warmup to every framework and retains continuous profiling; changes between campaigns are not isolated Bext code improvements.

[Raw per-thread samples and access buckets](analysis.json), [CPU audit](cpu.json), [load result](oha.json), [provenance](provenance.json). All load responses are HTTP 200, proof timestamps stay fresh and affinity checks pass. The sample interval and clock-tick resolution are recorded. Production is unchanged.
