# Renderer-only JavaScript profile

[Bext PR #423](https://github.com/benfavre/bext/pull/423) adds a standalone profiling example. Its release build and 20-second run pass; the last result has 24 product markers and a positive fresh timestamp. The CPU profile uses CPU 10, no affinity violations and no lost samples. V8 perf maps resolve JavaScript functions such as `runRoute`, `walkMarkup`, `h`, and `URL`.

This is a renderer diagnostic, not HTTP throughput. V8 perf flags change code compaction/stack instrumentation; the synchronous public API also copies its caller's bundle. It excludes controller/HTTP/subprocess costs. Do not interpret its iteration count as the framework's RPS or attribute its caller-side copy cost to the subprocess worker. Source/native/SDK inputs are the qualified accepted versions plus the example; rejected runtime prototypes are excluded.

[Qualification](qualification.json), [flat report](flat-report.txt), [inclusive report](inclusive-report.txt), [JIT map](jit.map), [CPU audit](cpu.json). Substantial unresolved/incomplete stacks limit inclusive attribution. The captured self-contained bundle, HTML and raw perf data stay local with hashes and paths in [retention metadata](retention.json). The initial fixture used an underscore prefix that routing treats as private; that capture failed before any renderer profile and is recorded separately.
