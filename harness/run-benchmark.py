#!/usr/bin/env python3
"""Repeatable production SSR sweep; only stop processes started by this runner."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import socket
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
FRAMEWORKS = ["next", "remix", "astro", "qwik", "bext"]
LOAD_URL_COUNT = 1_000_000
PERFORMANCE_FLAGS = {name: {"0", "1"} for name in [
    "BEXT_V8_MULTIPLEX", "BEXT_PRISM_PREPARED_PAGES", "BEXT_V8_LEGACY_HASH_HINT",
    "BEXT_PRISM_TOKEN_SCAN", "BEXT_PRISM_NATIVE_HTML_SCAN",
]}
PERFORMANCE_FLAGS["BEXT_V8_PREPARED_TEXT"] = {"0", "2", "3", "4"}
PERFORMANCE_FLAGS["BEXT_V8_MAX_SEMI_SPACE_MB"] = {"4", "8", "16"}
PERFORMANCE_FLAGS["BEXT_V8_BY_HASH_REPLY_TRANSPORT"] = {"0", "1", "2"}
PACKAGES = {
    "next": ["next", "react", "react-dom"],
    "remix": ["react-router", "@react-router/node", "@react-router/serve", "react", "react-dom", "vite"],
    "astro": ["astro", "@astrojs/node", "vite"],
    "qwik": ["@builder.io/qwik", "@builder.io/qwik-city", "vite", "express"],
}


def utc():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def capture(args, cwd=ROOT):
    return subprocess.check_output(args, cwd=cwd, text=True, stderr=subprocess.DEVNULL).strip()


def versions(frameworks):
    result = {}
    for fw in frameworks:
        result[fw] = {}
        for package in PACKAGES.get(fw, []):
            path = ROOT / "apps" / fw / "node_modules" / package / "package.json"
            result[fw][package] = json.loads(path.read_text())["version"]
    return result


def cpu_list(value):
    cpus = set()
    for part in value.split(","):
        bounds = part.split("-")
        if len(bounds) == 1:
            cpus.add(int(part))
        elif len(bounds) == 2:
            start, end = map(int, bounds)
            if start > end:
                raise argparse.ArgumentTypeError("CPU ranges must be ascending")
            cpus.update(range(start, end + 1))
        else:
            raise argparse.ArgumentTypeError("expected CPU list such as 2 or 2,4-6")
    if not cpus or min(cpus) < 0:
        raise argparse.ArgumentTypeError("CPU numbers must be non-negative")
    return sorted(cpus)


def performance_flag(value):
    key, separator, setting = value.partition("=")
    if not separator or key not in PERFORMANCE_FLAGS or setting not in PERFORMANCE_FLAGS[key]:
        allowed = ", ".join(f"{name}={'|'.join(sorted(values))}" for name, values in sorted(PERFORMANCE_FLAGS.items()))
        raise argparse.ArgumentTypeError("expected an allowed performance setting: " + allowed)
    return key, setting


def process_tree(pid):
    processes = {}
    for directory in Path("/proc").glob("[0-9]*"):
        try:
            fields = (directory / "stat").read_text().rpartition(")")[2].split()
            processes[int(directory.name)] = {
                "pid": int(directory.name), "parent": int(fields[1]),
                "startTicks": int(fields[19]), "cpuTicks": int(fields[11]) + int(fields[12]),
            }
        except (OSError, ValueError, IndexError):
            continue
    selected = {pid}
    while True:
        descendants = {p for p, data in processes.items() if data["parent"] in selected}
        if descendants <= selected:
            break
        selected |= descendants
    result = []
    for child in selected:
        if child not in processes:
            continue
        data = processes[child]
        affinities = []
        for task in Path(f"/proc/{child}/task").glob("[0-9]*"):
            try:
                affinities.append(sorted(os.sched_getaffinity(int(task.name))))
            except ProcessLookupError:
                continue
        data["threadCount"] = len(affinities)
        data["threadCpuAffinities"] = sorted({tuple(mask) for mask in affinities})
        result.append(data)
    return result


class CpuAudit:
    """Sample the server and descendants, including every thread's CPU mask."""
    def __init__(self, pid, allowed=None):
        self.pid, self.allowed = pid, set(allowed) if allowed else None
        self.initial, self.latest = {}, {}
        self.samples, self.violations, self.errors = [], [], []
        self.event = threading.Event()
        self.thread = None

    def sample(self):
        snapshot = process_tree(self.pid)
        if not snapshot:
            raise RuntimeError("server process disappeared during CPU audit")
        first = not self.samples
        for process in snapshot:
            key = f"{process['pid']}:{process['startTicks']}"
            if first:
                self.initial[key] = process["cpuTicks"]
            self.latest[key] = process
            for mask in process["threadCpuAffinities"]:
                if self.allowed is not None and not set(mask) <= self.allowed:
                    self.violations.append({"pid": process["pid"], "cpuAffinity": mask})
        self.samples.append({"elapsedSeconds": time.perf_counter() - self.started,
                             "processCount": len(snapshot),
                             "threadCount": sum(p["threadCount"] for p in snapshot)})

    def start(self):
        self.started = time.perf_counter()
        self.sample()

        def monitor():
            while not self.event.wait(0.25):
                try:
                    self.sample()
                except Exception as error:
                    self.errors.append(str(error))
                    return

        self.thread = threading.Thread(target=monitor, daemon=True)
        self.thread.start()

    def stop(self):
        self.event.set()
        if self.thread:
            self.thread.join(timeout=5)
            if self.thread.is_alive():
                raise RuntimeError("CPU audit thread did not stop")
        self.sample()
        wall = time.perf_counter() - self.started
        tick_rate = os.sysconf("SC_CLK_TCK")
        processes = [{**data, "cpuSeconds": (data["cpuTicks"] - self.initial.get(key, 0)) / tick_rate}
                     for key, data in self.latest.items()]
        cpu_seconds = sum(p["cpuSeconds"] for p in processes)
        return {"method": "sampled /proc server process tree; all thread affinity masks",
                "sampleIntervalSeconds": 0.25, "clockTicksPerSecond": tick_rate,
                "wallSeconds": wall, "cpuSeconds": cpu_seconds, "averageCpuCores": cpu_seconds / wall,
                "requestedCpuAffinity": sorted(self.allowed) if self.allowed else None,
                "affinityViolations": self.violations, "errors": self.errors,
                "samples": self.samples, "processes": processes}


def metadata(args):
    cpu = next(line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
               if line.startswith("model name"))
    files = capture(["git", "ls-files", "apps", "harness", "products.json", "package.json", "package-lock.json"]).splitlines()
    # Include new, uncommitted harness files in the experiment identity, too.
    files = sorted(set(files) | {"package-lock.json"} | {str(p.relative_to(ROOT)) for p in (ROOT / "harness").glob("*") if p.is_file()})
    result = {
        "startedAt": utc(), "host": platform.node(), "os": platform.platform(),
        "cpu": cpu, "logicalCpus": os.cpu_count(), "loadAverage": os.getloadavg(),
        "node": capture(["node", "--version"]), "npm": capture(["npm", "--version"]),
        "puppeteer": json.loads((ROOT / "node_modules/puppeteer/package.json").read_text())["version"],
        "oha": capture(["oha", "--version"]), "python": platform.python_version(),
        "gitCommit": capture(["git", "rev-parse", "HEAD"]),
        "sourceSha256": {name: sha256(ROOT / name) for name in files if (ROOT / name).is_file()},
        "versions": versions(args.frameworks),
        "parameters": {"repeats": args.repeats, "durationSeconds": args.duration,
                       "concurrency": args.concurrency, "coldSamples": args.cold_samples,
                       "warmupSeconds": 2, "httpVersion": "1.1", "uniqueLoadUrls": False,
                       "loadUrlPoolSize": LOAD_URL_COUNT, "loadUrlSelection": "random with replacement",
                       "waitForOngoingRequests": True, "underLoadSamples": 20},
        "cpuBudget": {"serverCpus": args.server_cpus, "clientCpus": args.client_cpus,
                      "runnerCpuAffinity": sorted(os.sched_getaffinity(0)),
                      "bextV8Workers": args.bext_v8_workers, "bextHttpWorkers": args.bext_http_workers},
    }
    if "bext" in args.frameworks:
        binary = Path(shutil.which(os.environ.get("BEXT_BIN", "bext-server")) or "")
        shared = Path(os.environ.get("BEXT_SHARED_FRAMEWORK_DIR", "/usr/share/bext/framework"))
        if not binary.is_file() or not shared.is_dir():
            raise RuntimeError("bext requires BEXT_BIN and BEXT_SHARED_FRAMEWORK_DIR; explicitly omit it with --frameworks to run fewer apps")
        framework_files = sorted(p for p in shared.rglob("*") if p.is_file() and not any(
            part in {"node_modules", ".git", ".bext"} for part in p.relative_to(shared).parts))
        hashes = {str(p.relative_to(shared)): sha256(p) for p in framework_files}
        result["bext"] = {
            "version": capture([str(binary), "--version"]), "binarySha256": sha256(binary),
            "binaryBytes": binary.stat().st_size,
            "frameworkSha256": hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest(),
            "frameworkFileSha256": hashes,
            "overrides": {"BEXT_PRISM_RENDER_CACHE": "0", "BEXT_V8_POOL_PER_WORKER_CAP": "64",
                          "BEXT_V8_POOL_QUEUE_DEPTH": "256"},
        }
        if args.bext_v8_workers is not None:
            result["bext"]["overrides"]["BEXT_V8_POOL_SIZE"] = str(args.bext_v8_workers)
        if args.bext_http_workers is not None:
            result["bext"]["overrides"]["BEXT_HTTP_WORKERS"] = str(args.bext_http_workers)
        result["bext"]["overrides"].update(dict(args.bext_flag))
        if args.bext_log_filter is not None:
            result["bext"]["overrides"]["RUST_LOG"] = args.bext_log_filter
    return result


def port_is_free(port):
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError as error:
            raise RuntimeError(f"port {port} is occupied; no existing process will be killed") from error


@contextmanager
def server(fw, bench, directory, label, args=None):
    port_is_free(bench["port"])
    with (directory / f"{fw}.{label}.log").open("w") as log:
        started = time.perf_counter()
        command = ["bash", "-c", bench["start"]]
        env = {**os.environ, "NODE_ENV": "production"}
        if args is not None:
            if args.server_cpus:
                command = ["taskset", "--cpu-list", ",".join(map(str, args.server_cpus))] + command
            if fw == "bext":
                if args.bext_v8_workers is not None:
                    env["BEXT_V8_POOL_SIZE"] = str(args.bext_v8_workers)
                if args.bext_http_workers is not None:
                    env["BEXT_HTTP_WORKERS"] = str(args.bext_http_workers)
                env.update(dict(getattr(args, "bext_flag", [])))
                if getattr(args, "bext_log_filter", None) is not None:
                    env["RUST_LOG"] = args.bext_log_filter
        proc = subprocess.Popen(command, cwd=ROOT / "apps" / fw, env=env,
                                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            yield proc, started
        finally:
            # A private process group includes shell grandchildren and V8 workers.
            # Never look up and kill an arbitrary listener by port.
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait(timeout=5)


def request(url):
    with urllib.request.urlopen(url, timeout=3) as response:
        return response.status, response.read().decode()


def ready(proc, url, started):
    deadline = started + 60
    while time.perf_counter() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"server exited with {proc.returncode}; see its server log")
        try:
            status, _ = request(url)
            if status == 200:
                return (time.perf_counter() - started) * 1000
        except (OSError, TimeoutError):
            pass
        time.sleep(0.005)
    raise RuntimeError(f"server never returned HTTP 200 at {url}")


def stamp(url):
    status, html = request(url)
    match = re.search(r'data-rendered-at="(\d+)"', html)
    if status != 200 or not match or int(match[1]) <= 0:
        raise RuntimeError(f"missing live render timestamp at {url}")
    return match[1]


def build_size(fw, bench):
    paths = bench.get("buildDirs", [bench.get("buildDir")])
    totals = {}
    for name in paths:
        path = ROOT / "apps" / fw / name
        if not path.is_dir():
            raise RuntimeError(f"build output missing: {path}")
        # Next's compiler cache and tracing diagnostics are not deployment output.
        totals[name] = sum(p.stat().st_size for p in path.rglob("*") if p.is_file() and not (
            fw == "next" and p.relative_to(path).parts[0] in {"cache", "diagnostics"}))
    return {"bytes": sum(totals.values()), "directories": totals,
            "excludes": ["cache", "diagnostics"] if fw == "next" else []}


def measure(fw, bench, directory, args):
    prefix = directory / fw
    url = f"http://127.0.0.1:{bench['port']}/"
    environment = {"startedAt": utc(), "loadBefore": os.getloadavg(), "startCommand": bench["start"]}
    print(f"  {fw}: {args.cold_samples} process starts", flush=True)
    cold = []
    for index in range(args.cold_samples):
        with server(fw, bench, directory, f"cold-{index + 1}", args) as (proc, started):
            cold.append(round(ready(proc, url, started), 3))
    write_json(prefix.with_suffix(".cold.json"), {"samplesMs": cold, "medianMs": statistics.median(cold)})
    with server(fw, bench, directory, "server", args) as (proc, started):
        ready(proc, url, started)
        r1 = stamp(url)
        time.sleep(1.1)
        r2 = stamp(url)
        if r1 == r2:
            raise RuntimeError(f"{fw}: idle render timestamp did not change")
        with tempfile.NamedTemporaryFile(mode="w", prefix="same-app-urls-", suffix=".txt") as urls:
            # oha samples this file randomly, with replacement. Distinct entries
            # do not guarantee distinct requests; explicitly disable response
            # caches and verify fresh render timestamps during the load test.
            urls.writelines(f"{url}?r={index}\n" for index in range(LOAD_URL_COUNT))
            urls.flush()
            base = ["oha", "-c", str(args.concurrency), "-w", "--no-tui", "--http-version", "1.1",
                    "--output-format", "json", "--urls-from-file", urls.name]
            oha_env = {**os.environ, "NO_COLOR": "true"}
            with prefix.with_suffix(".warmup.json").open("w") as output, prefix.with_suffix(".warmup.log").open("w") as errors:
                subprocess.run(base + ["-z", "2s"], stdout=output, stderr=errors,
                               env=oha_env, check=True, timeout=30)
            samples = []
            print(f"  {fw}: {args.duration}s load, concurrency {args.concurrency}", flush=True)
            with prefix.with_suffix(".oha.json").open("w") as output, prefix.with_suffix(".oha.log").open("w") as errors:
                audit = CpuAudit(proc.pid, args.server_cpus)
                audit.start()
                load = None
                try:
                    load = subprocess.Popen(base + ["-z", f"{args.duration}s"], stdout=output, stderr=errors, env=oha_env)
                    time.sleep(1)
                    for index in range(20):
                        if load.poll() is not None:
                            raise RuntimeError("load test ended before proof sampling finished")
                        samples.append(stamp(f"{url}?r=proof-{index}"))
                        time.sleep(0.1)
                    if load.wait(timeout=args.duration + 30) != 0:
                        raise RuntimeError("oha failed; see its log")
                finally:
                    if load is not None and load.poll() is None:
                        load.terminate()
                        load.wait(timeout=5)
                    cpu = audit.stop()
                    write_json(prefix.with_suffix(".cpu.json"), cpu)
                if cpu["affinityViolations"] or cpu["errors"]:
                    raise RuntimeError(f"{fw}: CPU affinity audit failed; see {prefix}.cpu.json")
            oha = json.loads(prefix.with_suffix(".oha.json").read_text())
            statuses = oha["statusCodeDistribution"]
            if set(statuses) != {"200"} or not statuses["200"] or oha.get("errorDistribution") or oha["summary"]["successRate"] != 1:
                raise RuntimeError(f"{fw}: load errors or non-200s: {statuses}, {oha.get('errorDistribution')}")
        proof = {"r1": r1, "r2": r2, "loadSamples": samples, "loadDistinct": len(set(samples)),
                 "uncached": r1 != r2 and len(set(samples)) == 20}
        write_json(prefix.with_suffix(".proof"), proof)
        if not proof["uncached"]:
            raise RuntimeError(f"{fw}: render timestamp was repeated under load")
        print(f"  {fw}: browser checks", flush=True)
        with prefix.with_suffix(".browser.json").open("w") as output, prefix.with_suffix(".browser.log").open("w") as errors:
            subprocess.run(["node", str(ROOT / "harness/h2h-measure.mjs"), url, fw],
                           stdout=output, stderr=errors, check=True, timeout=90)
        browser = json.loads(prefix.with_suffix(".browser.json").read_text())
        if not (browser["status"] == 200 and browser["ssrCards"] == 24 and browser["ssrProducts"] == 24
                and all(browser.get(key) for key in ["counterOk", "themeOk", "themePersistOk", "searchOk"])):
            raise RuntimeError(f"{fw}: failed SSR/browser contract; see {prefix}.browser.json")
        write_json(prefix.with_suffix(".build.json"), build_size(fw, bench))
    port_is_free(bench["port"])
    environment.update({"finishedAt": utc(), "loadAfter": os.getloadavg()})
    write_json(prefix.with_suffix(".environment.json"), environment)
    print(f"  {fw}: {oha['summary']['requestsPerSec']:,.0f} RPS, verified", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "results/runs" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--frameworks", nargs="+", choices=FRAMEWORKS, default=FRAMEWORKS)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--duration", type=int, default=8)
    parser.add_argument("--concurrency", type=int, default=50)
    parser.add_argument("--cold-samples", type=int, default=3)
    parser.add_argument("--server-cpus", type=cpu_list, help="CPU affinity for every server and its descendants")
    parser.add_argument("--client-cpus", type=cpu_list, help="CPU affinity for runner, oha and Chrome; use CPUs outside the server core")
    parser.add_argument("--bext-v8-workers", type=int, help="explicit BEXT_V8_POOL_SIZE (1–16)")
    parser.add_argument("--bext-http-workers", type=int, help="explicit BEXT_HTTP_WORKERS")
    parser.add_argument("--bext-log-filter", choices=["info", "warn"],
                        help="record and set RUST_LOG for bext; use to measure detailed tracing overhead")
    parser.add_argument("--bext-flag", action="append", type=performance_flag, default=[],
                        help="record and apply an allowlisted performance setting (NAME=value); response-cache controls are excluded")
    args = parser.parse_args()
    if min(args.repeats, args.concurrency, args.cold_samples) < 1 or args.duration < 4:
        parser.error("positive repeats/concurrency/cold samples and duration >= 4s required")
    available = os.sched_getaffinity(0)
    for cpus in [args.server_cpus, args.client_cpus]:
        if cpus and not set(cpus) <= available:
            parser.error(f"CPU mask is outside available CPUs: {sorted(available)}")
    if args.bext_v8_workers is not None and not 1 <= args.bext_v8_workers <= 16:
        parser.error("bext V8 worker count must be between 1 and 16")
    if args.bext_http_workers is not None and args.bext_http_workers < 1:
        parser.error("bext HTTP worker count must be positive")
    if args.client_cpus:
        os.sched_setaffinity(0, args.client_cpus)
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = {"schemaVersion": 1, "status": "running", "frameworks": args.frameworks,
                "repeats": args.repeats, "runs": [], "startedAt": utc()}
    write_json(args.output / "campaign.json", manifest)
    try:
        benches = {fw: json.loads((ROOT / "apps" / fw / "bench.json").read_text()) for fw in args.frameworks}
        for bench in benches.values():
            port_is_free(bench["port"])
        write_json(args.output / "metadata.json", metadata(args))
        for repeat in range(args.repeats):
            shift = (repeat * 2) % len(args.frameworks)
            order = args.frameworks[shift:] + args.frameworks[:shift]
            directory = args.output / f"run-{repeat + 1}"
            directory.mkdir()
            manifest["runs"].append({"directory": directory.name, "order": order})
            write_json(args.output / "campaign.json", manifest)
            print(f"Sweep {repeat + 1}/{args.repeats}: {', '.join(order)}", flush=True)
            for fw in order:
                measure(fw, benches[fw], directory, args)
        manifest["status"] = "complete"
    except Exception as error:
        manifest.update({"status": "failed", "error": str(error)})
        print(f"FAILED: {error}", file=sys.stderr, flush=True)
    finally:
        manifest["finishedAt"] = utc()
        write_json(args.output / "campaign.json", manifest)
        print(f"Evidence: {args.output}", flush=True)
    return 0 if manifest["status"] == "complete" else 1


if __name__ == "__main__":
    sys.exit(main())
