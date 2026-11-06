#!/usr/bin/env python3
"""Verify shared-memory activation in an owned benchmark process tree."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("runner", ROOT / "harness/run-benchmark.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", type=int, choices=[0, 1, 2], required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--server-cpus", type=runner.cpu_list, default=[10])
    parser.add_argument("--client-cpus", type=runner.cpu_list, default=runner.cpu_list("0-9,11-21,23"))
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, args.client_cpus)
    options = SimpleNamespace(server_cpus=args.server_cpus, bext_v8_workers=4, bext_http_workers=1,
        bext_log_filter="warn", bext_flag=[
            ("BEXT_V8_MULTIPLEX", "0"), ("BEXT_PRISM_PREPARED_PAGES", "1"),
            ("BEXT_V8_LEGACY_HASH_HINT", "1"), ("BEXT_PRISM_TOKEN_SCAN", "1"),
            ("BEXT_V8_PREPARED_TEXT", "2"), ("BEXT_PRISM_NATIVE_HTML_SCAN", "1"),
            ("BEXT_V8_BY_HASH_REPLY_TRANSPORT", str(args.mode)),
        ])
    bench = json.loads((ROOT / "apps/bext/bench.json").read_text())
    url = f"http://127.0.0.1:{bench['port']}/"
    result = dict(status="running", mode=args.mode, flags=dict(options.bext_flag),
                  productionChanged=False, observations=[])
    try:
        with runner.server("bext", bench, args.output, "activation", options) as (proc, started):
            runner.ready(proc, url, started)
            audit = runner.CpuAudit(proc.pid, args.server_cpus)
            audit.start()
            try:
                stamps = [runner.stamp(url + f"?r=transport-proof-{index}") for index in range(40)]
                time.sleep(0.05)
                processes = runner.process_tree(proc.pid)
                owned_pids = {process["pid"] for process in processes}
                workers = set()
                for process in processes:
                    pid = process["pid"]
                    mappings = []
                    for line in Path(f"/proc/{pid}/maps").read_text().splitlines():
                        path = line.split()[-1]
                        if path.startswith("/dev/shm/bext-v8-shm-"):
                            owner_pid = int(path.rsplit("-", 1)[1])
                            if owner_pid not in owned_pids:
                                raise RuntimeError("mapping belongs to a process outside the owned tree")
                            if owner_pid == pid:
                                workers.add(pid)
                            mappings.append(dict(path=path, ownerPid=owner_pid,
                                                 permissions=line.split()[1]))
                    result["observations"].append(dict(pid=pid, mappings=mappings))
                result["workerPids"] = sorted(workers)
                readers = [row for row in result["observations"]
                           if row["pid"] not in workers and row["mappings"]]
                result["controllerMappings"] = readers
                result["timestampSamples"] = stamps
                if len(workers) != 4:
                    raise RuntimeError("expected four worker shared-memory regions")
                if bool(readers) != (args.mode == 2):
                    raise RuntimeError("controller mappings do not match requested transport")
                if len(set(stamps)) < 2:
                    raise RuntimeError("render timestamp did not change")
            finally:
                result["cpuAudit"] = audit.stop()
            if result["cpuAudit"]["affinityViolations"] or result["cpuAudit"]["errors"]:
                raise RuntimeError("CPU audit failed")
        result["status"] = "complete"
    except Exception as error:
        result.update(status="failed", error=str(error))
    finally:
        runner.write_json(args.output / "proof.json", result)
    print(json.dumps({key: value for key, value in result.items()
                      if key not in {"cpuAudit", "observations", "timestampSamples"}}, indent=2))
    return 0 if result["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
