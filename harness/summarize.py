#!/usr/bin/env python3
"""Summarize one complete campaign; incomplete or failed evidence is an error."""
import argparse
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parent.parent
NAMES = {"next": "Next.js", "remix": "React Router (Remix)", "astro": "Astro",
         "qwik": "Qwik", "bext": "bext (PRISM)"}


def read(path):
    return json.loads(path.read_text())


def summarize_campaign(path):
    campaign = read(path / "campaign.json")
    metadata = read(path / "metadata.json") if (path / "metadata.json").exists() else {}
    cpu_budget = metadata.get("cpuBudget")
    if campaign["status"] != "complete" or len(campaign["runs"]) != campaign["repeats"]:
        raise ValueError("campaign is incomplete or failed")
    if len({run["directory"] for run in campaign["runs"]}) != campaign["repeats"]:
        raise ValueError("campaign repeats must refer to distinct run directories")
    rows = []
    for fw in campaign["frameworks"]:
        runs, cold_samples = [], []
        for run in campaign["runs"]:
            if sorted(run["order"]) != sorted(campaign["frameworks"]):
                raise ValueError("each sweep must measure every selected framework exactly once")
            prefix = path / run["directory"] / fw
            browser = read(prefix.with_suffix(".browser.json"))
            proof = read(prefix.with_suffix(".proof"))
            oha = read(prefix.with_suffix(".oha.json"))
            build = read(prefix.with_suffix(".build.json"))
            cold = read(prefix.with_suffix(".cold.json"))
            if not (browser["status"] == 200 and browser["ssrCards"] == 24 and browser["ssrProducts"] == 24
                    and all(browser.get(key) for key in ["counterOk", "themeOk", "themePersistOk", "searchOk"])
                    and not browser.get("resourceErrors")):
                raise ValueError(f"{prefix}: browser/SSR contract failed")
            if not (proof["uncached"] and proof["r1"] and proof["r2"] and proof["r1"] != proof["r2"]
                    and len(proof["loadSamples"]) == 20 and len(set(proof["loadSamples"])) == 20
                    and all(proof["loadSamples"])):
                raise ValueError(f"{prefix}: uncached proof failed")
            if not (set(oha["statusCodeDistribution"]) == {"200"} and oha["statusCodeDistribution"]["200"] > 0
                    and oha["summary"]["successRate"] == 1 and not oha.get("errorDistribution")):
                raise ValueError(f"{prefix}: HTTP/load errors")
            if not cold["samplesMs"] or min(cold["samplesMs"]) <= 0 or build["bytes"] <= 0:
                raise ValueError(f"{prefix}: missing cold/build measurements")
            cpu = None
            if cpu_budget is not None:
                cpu = read(prefix.with_suffix(".cpu.json"))
                expected = cpu_budget["serverCpus"]
                if cpu["errors"] or cpu["affinityViolations"] or len(cpu["samples"]) < 2:
                    raise ValueError(f"{prefix}: CPU audit failed")
                if cpu["requestedCpuAffinity"] != expected or cpu["cpuSeconds"] <= 0:
                    raise ValueError(f"{prefix}: CPU audit does not match campaign budget")
                if expected and any(not set(mask) <= set(expected) for process in cpu["processes"]
                                    for mask in process["threadCpuAffinities"]):
                    raise ValueError(f"{prefix}: server thread escaped CPU mask")
            cold_samples.extend(cold["samplesMs"])
            runs.append({
                "run": run["directory"], "rps": oha["summary"]["requestsPerSec"],
                "ttfb_ms": oha["firstBytePercentiles"]["p50"] * 1000,
                "p99_ms": oha["latencyPercentiles"]["p99"] * 1000,
                "client_js_gz_kb": browser["clientJsGzB"] / 1024,
                "initial_client_js_gz_kb": browser["initialClientJsGzB"] / 1024,
                "js_reqs": browser["jsReqs"], "build_kb": build["bytes"] / 1024,
                "http_200_responses": oha["statusCodeDistribution"]["200"],
            })
            if cpu:
                runs[-1]["average_cpu_cores"] = cpu["averageCpuCores"]
                runs[-1]["cpu_ms_per_request"] = cpu["cpuSeconds"] / oha["statusCodeDistribution"]["200"] * 1000
        row = {"framework": NAMES[fw], "id": fw, "run_count": len(runs), "runs": runs,
               "rps_min": round(min(r["rps"] for r in runs)), "rps_max": round(max(r["rps"] for r in runs)),
               "cold_ms": round(statistics.median(cold_samples), 2), "cold_samples_ms": cold_samples,
               "ok": "CTS", "theme_persistence": True, "uncached": True,
               "ssr_cards": 24, "ssr_products": 24, "success": 1.0}
        for key in ["rps", "ttfb_ms", "p99_ms", "client_js_gz_kb", "initial_client_js_gz_kb", "js_reqs", "build_kb"]:
            value = statistics.median(r[key] for r in runs)
            row[key] = round(value) if key in {"rps", "js_reqs"} else round(value, 2)
        if cpu_budget is not None:
            row["server_cpu_affinity"] = cpu_budget["serverCpus"]
            for key in ["average_cpu_cores", "cpu_ms_per_request"]:
                row[key] = round(statistics.median(r[key] for r in runs), 4)
        rows.append(row)
    return {"aggregation": "median of equal repeat sweeps; cold start is median of all process starts",
            "startedAt": campaign["startedAt"], "finishedAt": campaign["finishedAt"],
            "cpuBudget": cpu_budget, "frameworks": rows}


def table(summary):
    lines = ["| Framework | Client JS (KiB gz) | TTFB p50 (ms) | RPS median | RPS min–max | p99 (ms) | Process start (ms) | Output (KiB) | C/T/S |",
             "|---|---:|---:|---:|---:|---:|---:|---:|:---:|"]
    for row in sorted(summary["frameworks"], key=lambda r: r["rps"], reverse=True):
        lines.append(f"| {row['framework']} | {row['client_js_gz_kb']:.2f} | {row['ttfb_ms']:.2f} | "
                     f"{row['rps']:,} | {row['rps_min']:,}–{row['rps_max']:,} | {row['p99_ms']:.2f} | "
                     f"{row['cold_ms']:.0f} | {row['build_kb']:,.1f} | ✓ |")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign", nargs="?", type=Path)
    parser.add_argument("--publish", action="store_true", help="also update results/results.json and results/latest.json")
    args = parser.parse_args()
    if args.campaign is None:
        candidates = list((ROOT / "results/runs").glob("*/campaign.json"))
        if not candidates:
            parser.error("no campaigns found; run harness/run-all.sh first")
        # Select the latest attempt, including failures, so an old success cannot
        # silently stand in for a failed re-run.
        args.campaign = max(candidates, key=lambda p: read(p)["startedAt"]).parent
    path = args.campaign.resolve()
    try:
        summary = summarize_campaign(path)
    except (ValueError, KeyError, OSError) as error:
        print(f"Cannot publish benchmark: {error}", file=sys.stderr)
        return 1
    (path / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    (path / "table.md").write_text(table(summary))
    if args.publish:
        campaign_name = str(path.relative_to(ROOT / "results"))
        (ROOT / "results/results.json").write_text(json.dumps(summary["frameworks"], indent=2) + "\n")
        (ROOT / "results/latest.json").write_text(json.dumps({"campaign": campaign_name,
                                                            "finishedAt": summary["finishedAt"]}, indent=2) + "\n")
    print(table(summary))
    print("C/T/S plus theme persistence, all 24 SSR products, uncached idle/load proof and 100% HTTP 200 verified.")
    print(f"Raw evidence: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
