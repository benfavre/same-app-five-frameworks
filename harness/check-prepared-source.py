#!/usr/bin/env python3
"""Check source invalidation in disposable copies, with prepared pages off/on."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import time
from types import SimpleNamespace
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("runner", ROOT / "harness/run-benchmark.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--server-cpu", type=int, default=10)
    parser.add_argument("--port", type=int, default=18105)
    parser.add_argument("--legacy-hash-hint", type=int, choices=[0, 1], default=0)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    available = os.sched_getaffinity(0)
    if args.server_cpu not in available:
        parser.error("requested server CPU is unavailable")
    siblings = runner.cpu_list(Path(f"/sys/devices/system/cpu/cpu{args.server_cpu}/topology/thread_siblings_list").read_text().strip())
    client_cpus = available - set(siblings)
    if not client_cpus:
        parser.error("need another physical core for the client")
    os.sched_setaffinity(0, client_cpus)
    result = {"status": "running", "cases": [], "serverCpu": args.server_cpu,
              "clientCpus": sorted(client_cpus), "fixtureCopiesOnly": True,
              "liveReload": True, "watcherWarmupSeconds": 1.25,
              "legacyHashHint": args.legacy_hash_hint,
              "note": "Source edits use the documented one-second watcher in disposable fixtures; timed benchmarks retain live_reload=false."}
    original_root = runner.ROOT
    url = f"http://127.0.0.1:{args.port}/"

    def observe(mode, name, predicate):
        started = time.monotonic()
        while time.monotonic() - started < 10:
            status, body = runner.request(url)
            if status == 200 and predicate(body):
                stamp = re.search(r'data-rendered-at="(\d+)"', body)
                if not stamp or int(stamp[1]) <= 0:
                    raise RuntimeError("render timestamp missing")
                result["cases"].append({"preparedPages": mode, "case": name, "status": status,
                                        "renderedAt": stamp[1], "elapsedMs": round((time.monotonic() - started) * 1000, 2)})
                return body
            time.sleep(0.1)
        raise RuntimeError(f"prepared={mode}: {name} did not reflect current source")

    def observe_api(mode, name, marker):
        started = time.monotonic()
        for method in ["GET", "POST"]:
            for index in range(12):
                value = f"{name}-{method}-{index}"
                data = json.dumps({"value": value}).encode() if method == "POST" else None
                req = urllib.request.Request(url + "api/hash-probe?value=" + value,
                    data=data, headers={"Content-Type": "application/json"}, method=method)
                deadline = time.monotonic() + 10
                while True:
                    with urllib.request.urlopen(req, timeout=3) as response:
                        actual = json.load(response)
                    if actual == {"code": marker, "value": value}:
                        break
                    if time.monotonic() >= deadline:
                        raise RuntimeError(f"{name}: {method} returned stale source or request data: {actual}")
                    time.sleep(0.1)
        result["cases"].append({"preparedPages": mode, "case": name,
            "requests": 24, "methods": ["GET", "POST"], "code": marker,
            "elapsedMs": round((time.monotonic() - started) * 1000, 2)})

    try:
        for enabled in [0, 1]:
            with tempfile.TemporaryDirectory(prefix="prepared-source-", dir=ROOT / ".benchmark-runtime") as directory:
                fixture_root = Path(directory)
                app = fixture_root / "apps/bext"
                app.parent.mkdir()
                shutil.copytree(ROOT / "apps/bext", app, ignore=shutil.ignore_patterns(".bext", "node_modules"))
                config = app / "bext.config.toml"
                config_source = config.read_text()
                assert "live_reload = false" in config_source
                config.write_text(config_source.replace("live_reload = false", "live_reload = true"))
                api = app / "src/app/api/hash-probe/route.ts"
                api.parent.mkdir(parents=True)
                api_source = '''export const dynamic = "force-dynamic";
export async function GET(req: Request) {
  return {code: "original", value: new URL(req.url).searchParams.get("value")};
}
export async function POST(req: Request) {
  const body = await req.json();
  return {code: "original", value: body.value};
}
'''
                api.write_text(api_source)
                runner.ROOT = fixture_root
                bench = json.loads((app / "bench.json").read_text())
                bench["start"] = bench["start"].replace(f":{bench['port']}", f":{args.port}")
                bench["port"] = args.port
                options = SimpleNamespace(server_cpus=[args.server_cpu], bext_v8_workers=4, bext_http_workers=1,
                    bext_flag=[("BEXT_PRISM_PREPARED_PAGES", str(enabled)), ("BEXT_V8_MULTIPLEX", "0"),
                               ("BEXT_V8_LEGACY_HASH_HINT", str(args.legacy_hash_hint))])
                page, layout, products = [app / p for p in ["src/app/page.tsx", "src/app/layout.tsx", "src/lib/products.ts"]]
                with runner.server("bext", bench, args.output.parent, f"freshness-{enabled}", options) as (proc, started):
                    runner.ready(proc, url, started)
                    # The watcher's first one-second scan establishes its
                    # baseline; edit only after that initial snapshot exists.
                    time.sleep(1.25)
                    observe(enabled, "initial", lambda b: "<h1>Widget Showcase</h1>" in b)
                    observe_api(enabled, "api-fresh-request-data", "original")
                    api.write_text(api_source.replace('"original"', '"changed"'))
                    observe_api(enabled, "api-source-edit", "changed")
                    source = page.read_text()
                    assert "<h1>Widget Showcase</h1>" in source
                    page.write_text(source.replace("<h1>Widget Showcase</h1>", "<h1>Prepared Page Change</h1>"))
                    observe(enabled, "page-edit", lambda b: "<h1>Prepared Page Change</h1>" in b)
                    source = layout.read_text()
                    assert "Widget Showcase — bext (PRISM)" in source
                    changed_layout = source.replace("Widget Showcase — bext (PRISM)", "Prepared Layout Change")
                    layout.write_text(changed_layout)
                    observe(enabled, "layout-edit", lambda b: "<title>Prepared Layout Change</title>" in b)
                    source = products.read_text()
                    assert "Nimbus Speaker 1" in source
                    products.write_text(source.replace("Nimbus Speaker 1", "Fresh Product Marker", 1))
                    observe(enabled, "imported-data-edit", lambda b: ">Fresh Product Marker<" in b)
                    layout.unlink()
                    observe(enabled, "layout-delete", lambda b: "<h1>Prepared Page Change</h1>" in b and "Prepared Layout Change" not in b)
                    layout.write_text(changed_layout.replace("Prepared Layout Change", "Prepared Layout Readded"))
                    first = observe(enabled, "layout-add", lambda b: "<title>Prepared Layout Readded</title>" in b)
                    first_stamp = re.search(r'data-rendered-at="(\d+)"', first)[1]
                    time.sleep(0.02)
                    observe(enabled, "render-stays-fresh", lambda b: f'data-rendered-at="{first_stamp}"' not in b)
                runner.port_is_free(args.port)
        result["status"] = "complete"
    except Exception as error:
        result.update(status="failed", error=str(error))
    finally:
        runner.ROOT = original_root
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
