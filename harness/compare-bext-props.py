#!/usr/bin/env python3
"""Compare original/control/direct page-props encoding in three balanced blocks."""
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
ARMS = ["original", "rebuilt-off", "rebuilt-on"]


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--framework", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--server-cpus", default="10")
    parser.add_argument("--client-cpus", default="0-9,11-21,23")
    parser.add_argument("--duration", type=int, default=15)
    parser.add_argument("--warmup-seconds", type=int, default=20)
    parser.add_argument("--lock-file", type=Path)
    args = parser.parse_args()
    for binary in [args.original, args.candidate]:
        if not binary.is_file() or not os.access(binary, os.X_OK):
            parser.error(f"executable binary missing: {binary}")
    if not args.framework.is_dir():
        parser.error("shared framework directory missing")
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    lock = args.lock_file.open("a+") if args.lock_file else None
    result = {"status": "running", "method": "three balanced blocks: ABC/BCA/CAB",
              "preparedPages": True, "multiplex": False, "responseCache": False,
              "productionChanged": False, "warmupSeconds": args.warmup_seconds, "durationSeconds": args.duration, "cells": []}
    try:
        if lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
        identities = []
        sequence = 0
        for block in range(3):
            order = ARMS[block:] + ARMS[:block]
            for arm in order:
                sequence += 1
                directory = args.output / f"{sequence:02d}-{arm}"
                binary = args.original if arm == "original" else args.candidate
                env = {k: v for k, v in os.environ.items() if not k.startswith("BEXT_")}
                env.update(BEXT_BIN=str(binary.resolve()),
                           BEXT_SHARED_FRAMEWORK_DIR=str(args.framework.resolve()))
                command = [sys.executable, str(ROOT / "harness/run-benchmark.py"),
                    "--frameworks", "bext", "--repeats", "1", "--cold-samples", "1",
                    "--duration", str(args.duration), "--warmup-seconds", str(args.warmup_seconds), "--concurrency", "50",
                    "--server-cpus", args.server_cpus, "--client-cpus", args.client_cpus,
                    "--bext-v8-workers", "4", "--bext-http-workers", "1",
                    "--bext-flag", "BEXT_V8_MULTIPLEX=0",
                    "--bext-flag", "BEXT_PRISM_PREPARED_PAGES=1",
                    "--bext-log-filter", "warn",
                    "--bext-flag", "BEXT_V8_LEGACY_HASH_HINT=1",
                    "--bext-flag", "BEXT_PRISM_TOKEN_SCAN=1",
                    "--bext-flag", "BEXT_V8_PREPARED_TEXT=2",
                    "--bext-flag", "BEXT_PRISM_NATIVE_HTML_SCAN=1",
                    "--bext-flag", "BEXT_PRISM_DIRECT_PROPS_JSON=" + ("1" if arm == "rebuilt-on" else "0"),
                    "--output", str(directory)]
                print(f"Block {block + 1}: {arm}", flush=True)
                with (args.output / f"{sequence:02d}-{arm}.log").open("w") as log:
                    subprocess.run(command, cwd=ROOT, env=env, stdout=log,
                                   stderr=subprocess.STDOUT, check=True)
                summary = summarize_campaign(directory)
                write(directory / "summary.json", summary)
                metadata = json.loads((directory / "metadata.json").read_text())
                identity = {"source": metadata["sourceSha256"],
                            "framework": metadata["bext"]["frameworkSha256"],
                            "parameters": metadata["parameters"], "cpu": metadata["cpuBudget"]}
                if identities and identity != identities[0]:
                    raise RuntimeError("source, framework, workload or CPU budget drifted between cells")
                identities.append(identity)
                measurement = summary["frameworks"][0]["runs"][0]
                cell = {"block": block + 1, "arm": arm, "directory": directory.name,
                        "binarySha256": metadata["bext"]["binarySha256"], **measurement}
                result["cells"].append(cell)
                write(args.output / "analysis.json", result)
                print(f"  {measurement['rps']:,.0f} RPS, {measurement['cpu_ms_per_request']:.4f} CPU ms/request", flush=True)
        result["medians"] = {}
        for arm in ARMS:
            cells = [c for c in result["cells"] if c["arm"] == arm]
            if len({c["binarySha256"] for c in cells}) != 1:
                raise RuntimeError(f"binary changed between {arm} measurements")
            result["medians"][arm] = {
                key: statistics.median(c[key] for c in cells)
                for key in ["rps", "p99_ms", "cpu_ms_per_request"]}
            result["medians"][arm].update(rpsMin=min(c["rps"] for c in cells),
                                          rpsMax=max(c["rps"] for c in cells))
        if len({c["binarySha256"] for c in result["cells"] if c["arm"].startswith("rebuilt")}) != 1:
            raise RuntimeError("off/on measurements did not use the same candidate binary")
        off, on = [result["medians"][arm] for arm in ["rebuilt-off", "rebuilt-on"]]
        result.update(status="complete", rpsIncreasePercent=(on["rps"] / off["rps"] - 1) * 100,
                      cpuCostReductionPercent=(1 - on["cpu_ms_per_request"] / off["cpu_ms_per_request"]) * 100)
        result["pairedResults"] = []
        for block in range(1, 4):
            cells = {c["arm"]: c for c in result["cells"] if c["block"] == block}
            off, on = cells["rebuilt-off"], cells["rebuilt-on"]
            result["pairedResults"].append({"block": block,
                "rpsIncreasePercent": (on["rps"] / off["rps"] - 1) * 100,
                "cpuCostReductionPercent": (1 - on["cpu_ms_per_request"] / off["cpu_ms_per_request"]) * 100})
    except Exception as error:
        result.update(status="failed", error=str(error))
    finally:
        write(args.output / "analysis.json", result)
        if lock:
            lock.close()
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
