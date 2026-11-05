#!/usr/bin/env python3
"""Screen reply transports, then independently confirm the strongest candidate."""
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
BASE_FLAGS = {
    "BEXT_V8_MULTIPLEX": "0", "BEXT_PRISM_PREPARED_PAGES": "1",
    "BEXT_V8_LEGACY_HASH_HINT": "1", "BEXT_PRISM_TOKEN_SCAN": "1",
    "BEXT_V8_PREPARED_TEXT": "2", "BEXT_PRISM_NATIVE_HTML_SCAN": "1",
}


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["original", "candidate", "framework", "output"]:
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--server-cpus", default="10")
    parser.add_argument("--client-cpus", default="0-9,11-21,23")
    parser.add_argument("--duration", type=int, default=8)
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
    result = {"status": "running", "screen": [], "confirmation": [],
              "method": "five-cell exploratory screen; independent AB/BA/AB confirmation",
              "productionChanged": False, "responseCache": False,
              "flags": BASE_FLAGS, "detailedLogFilter": "warn"}
    identities = []

    def cell(phase, sequence, arm, mode, original=False, block=None):
        directory = args.output / f"{phase}-{sequence:02d}-{arm}"
        env = {k: v for k, v in os.environ.items() if not k.startswith("BEXT_")}
        binary = args.original if original else args.candidate
        env.update(BEXT_BIN=str(binary.resolve()),
                   BEXT_SHARED_FRAMEWORK_DIR=str(args.framework.resolve()))
        command = [sys.executable, str(ROOT / "harness/run-benchmark.py"),
            "--frameworks", "bext", "--repeats", "1", "--cold-samples", "1",
            "--duration", str(args.duration), "--concurrency", "50",
            "--server-cpus", args.server_cpus, "--client-cpus", args.client_cpus,
            "--bext-v8-workers", "4", "--bext-http-workers", "1",
            "--bext-log-filter", "warn", "--output", str(directory)]
        for key, value in {**BASE_FLAGS, "BEXT_V8_BY_HASH_REPLY_TRANSPORT": str(mode)}.items():
            command.extend(["--bext-flag", key + "=" + value])
        print(directory.name, flush=True)
        with directory.with_suffix(".log").open("w") as log:
            subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
        summary = summarize_campaign(directory)
        write(directory / "summary.json", summary)
        metadata = json.loads((directory / "metadata.json").read_text())
        identity = {key: metadata[key] for key in ["sourceSha256", "parameters", "cpuBudget"]}
        identity["framework"] = metadata["bext"]["frameworkSha256"]
        if identities and identity != identities[0]:
            raise RuntimeError("source, framework, workload or CPU budget changed between cells")
        identities.append(identity)
        measurement = summary["frameworks"][0]["runs"][0]
        row = dict(arm=arm, mode=mode, original=original, block=block, directory=directory.name,
                   binarySha256=metadata["bext"]["binarySha256"], **measurement)
        result[phase].append(row)
        write(args.output / "analysis.json", result)
        print(f"  {row['rps']:,.0f} RPS, {row['cpu_ms_per_request']:.4f} CPU ms/request", flush=True)
        return row

    try:
        if lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
        for sequence, (arm, mode, original) in enumerate([
            ("original", 0, True), ("copied", 0, False), ("vectored", 1, False),
            ("shared-memory", 2, False), ("original-repeat", 0, True),
        ], 1):
            cell("screen", sequence, arm, mode, original)
        best = max((row for row in result["screen"] if row["mode"] > 0), key=lambda row: row["rps"])
        result["selectedMode"] = best["mode"]
        result["screenSelection"] = "highest RPS among modes 1 and 2; screening cells excluded from confirmation"
        sequence = 0
        for block, order in enumerate([["control", "candidate"], ["candidate", "control"], ["control", "candidate"]], 1):
            for arm in order:
                sequence += 1
                cell("confirmation", sequence, arm, 0 if arm == "control" else best["mode"], block=block)
        if len({row["binarySha256"] for row in result["confirmation"]}) != 1:
            raise RuntimeError("confirmation did not use one candidate binary")
        result["medians"] = {arm: {
            key: statistics.median(row[key] for row in result["confirmation"] if row["arm"] == arm)
            for key in ["rps", "p99_ms", "cpu_ms_per_request"]
        } for arm in ["control", "candidate"]}
        control, candidate = [result["medians"][arm] for arm in ["control", "candidate"]]
        result.update(status="complete", rpsIncreasePercent=(candidate["rps"] / control["rps"] - 1) * 100,
                      cpuCostReductionPercent=(1 - candidate["cpu_ms_per_request"] / control["cpu_ms_per_request"]) * 100)
        result["pairedResults"] = []
        for block in range(1, 4):
            pair = {row["arm"]: row for row in result["confirmation"] if row["block"] == block}
            a, b = pair["control"], pair["candidate"]
            result["pairedResults"].append(dict(block=block, rpsIncreasePercent=(b["rps"] / a["rps"] - 1) * 100,
                cpuCostReductionPercent=(1 - b["cpu_ms_per_request"] / a["cpu_ms_per_request"]) * 100))
    except Exception as error:
        result.update(status="failed", error=str(error))
    finally:
        write(args.output / "analysis.json", result)
        if lock:
            lock.close()
    print(json.dumps({key: value for key, value in result.items() if key not in {"screen", "confirmation"}}, indent=2))
    return 0 if result["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
