#!/usr/bin/env python3
"""Measure accepted PRISM settings with three worker pools in rotating order."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys

from summarize import summarize_campaign

ROOT = Path(__file__).resolve().parents[1]
PROFILES = [("4v8-1http", 4, 1), ("12v8-12http", 12, 12), ("16v8-24http", 16, 24)]
FLAGS = {
    "BEXT_PRISM_PREPARED_PAGES": "1", "BEXT_V8_LEGACY_HASH_HINT": "1",
    "BEXT_V8_MULTIPLEX": "0", "BEXT_PRISM_TOKEN_SCAN": "1",
    "BEXT_V8_PREPARED_TEXT": "2", "BEXT_PRISM_NATIVE_HTML_SCAN": "1",
}


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--framework", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--lock-file", type=Path, required=True)
    parser.add_argument("--server-cpus", default="0-23")
    parser.add_argument("--client-cpus", default="0-23")
    parser.add_argument("--duration", type=int, default=15)
    parser.add_argument("--warmup-seconds", type=int, default=20)
    parser.add_argument("--concurrency", type=int, default=50)
    args = parser.parse_args()
    if not args.binary.is_file() or not os.access(args.binary, os.X_OK):
        parser.error("binary must be executable")
    if not args.framework.is_dir():
        parser.error("framework directory missing")
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    result = {"status": "running", "method": "three rotating blocks: ABC/BCA/CAB",
              "productionChanged": False, "responseCache": False,
              "clientColocated": True, "cells": []}
    env = {k: v for k, v in os.environ.items() if not k.startswith("BEXT_")}
    env.update(BEXT_BIN=str(args.binary.resolve()),
               BEXT_SHARED_FRAMEWORK_DIR=str(args.framework.resolve()))
    try:
        with args.lock_file.open("a+") as lock:
            print("Waiting for measurement lock", flush=True)
            fcntl.flock(lock, fcntl.LOCK_EX)
            identity = None
            for block in range(3):
                for name, v8, http in PROFILES[block:] + PROFILES[:block]:
                    directory = args.output / f"{len(result['cells']) + 1:02d}-{name}"
                    command = [sys.executable, str(ROOT / "harness/run-benchmark.py"),
                               "--frameworks", "bext", "--repeats", "1", "--cold-samples", "1",
                               "--duration", str(args.duration), "--warmup-seconds", str(args.warmup_seconds),
                               "--concurrency", str(args.concurrency), "--server-cpus", args.server_cpus,
                               "--client-cpus", args.client_cpus, "--bext-v8-workers", str(v8),
                               "--bext-http-workers", str(http), "--bext-log-filter", "warn",
                               "--output", str(directory)]
                    for key, value in FLAGS.items():
                        command += ["--bext-flag", key + "=" + value]
                    print(f"Block {block + 1}: {name}", flush=True)
                    with (args.output / f"{directory.name}.log").open("w") as log:
                        subprocess.run(command, cwd=ROOT, env=env, stdout=log,
                                       stderr=subprocess.STDOUT, check=True)
                    summary = summarize_campaign(directory)
                    write(directory / "summary.json", summary)
                    metadata = json.loads((directory / "metadata.json").read_text())
                    invariant = {"sources": metadata["sourceSha256"],
                                 "binary": metadata["bext"]["binarySha256"],
                                 "sdk": metadata["bext"]["frameworkSha256"],
                                 "parameters": metadata["parameters"],
                                 "serverCpus": metadata["cpuBudget"]["serverCpus"],
                                 "clientCpus": metadata["cpuBudget"]["clientCpus"]}
                    if identity is not None and invariant != identity:
                        raise RuntimeError("source, binary, SDK, workload or CPU budget drifted")
                    identity = invariant
                    cell = {"block": block + 1, "profile": name, "v8Workers": v8,
                            "httpWorkers": http, "directory": directory.name,
                            **summary["frameworks"][0]["runs"][0]}
                    result["cells"].append(cell)
                    write(args.output / "analysis.json", result)
                    print(f"  {cell['rps']:,.0f} RPS, {cell['average_cpu_cores']:.2f} CPUs, "
                          f"{cell['cpu_ms_per_request']:.4f} CPU ms/request", flush=True)
            result["identity"] = identity
            result["medians"] = {}
            for name, v8, http in PROFILES:
                cells = [c for c in result["cells"] if c["profile"] == name]
                result["medians"][name] = {
                    key: statistics.median(c[key] for c in cells)
                    for key in ["rps", "ttfb_ms", "p99_ms", "average_cpu_cores", "cpu_ms_per_request"]}
                result["medians"][name].update(
                    rpsMin=min(c["rps"] for c in cells), rpsMax=max(c["rps"] for c in cells),
                    v8Workers=v8, httpWorkers=http)
            result["status"] = "complete"
    except Exception as error:
        result.update(status="failed", error=str(error))
    finally:
        write(args.output / "analysis.json", result)
    return 0 if result["status"] == "complete" else 1


if __name__ == "__main__":
    sys.exit(main())
