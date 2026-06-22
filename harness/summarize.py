#!/usr/bin/env python3
# Combine the per-app raw outputs into one results.json + a printed table.
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = f"{ROOT}/results"
APPS = f"{ROOT}/apps"
ORDER = ["next", "remix", "astro", "qwik", "bext"]
NAMES = {"next": "Next.js", "remix": "Remix", "astro": "Astro", "qwik": "Qwik", "bext": "bext (PRISM)"}

def rd(p, default=None):
    try:
        with open(p) as f:
            return f.read().strip()
    except Exception:
        return default

def rj(p, default=None):
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return default

rows = []
for fw in ORDER:
    b = rj(f"{OUT}/{fw}.browser.json", {}) or {}
    oha = rj(f"{OUT}/{fw}.oha.json", {}) or {}
    summ = oha.get("summary", {})
    pct = oha.get("latencyPercentiles", {})
    fb = oha.get("firstBytePercentiles", {})
    bench = rj(f"{APPS}/{fw}/bench.json", {}) or {}
    build_bytes = bench.get("buildBytes", 0)
    cold = rd(f"{OUT}/{fw}.cold")
    ttfb = rd(f"{OUT}/{fw}.ttfb")
    row = {
        "framework": NAMES.get(fw, fw),
        "build_kb": round(build_bytes / 1024, 1) if build_bytes else None,
        "client_js_gz_kb": round(b.get("clientJsGzB", 0) / 1024, 2) if b else None,
        "js_reqs": b.get("jsReqs"),
        "ssr_cards": b.get("ssrCards"),
        "ttfb_ms": round(fb.get("p50", 0) * 1000, 2) if fb else (float(ttfb) if ttfb else None),
        "cold_ms": int(cold) if cold and cold.isdigit() else None,
        "rps": round(summ.get("requestsPerSec", 0)) if summ else None,
        "p99_ms": round(pct.get("p99", 0) * 1000, 2) if pct else None,
        "success": summ.get("successRate"),
        "tti_ms": b.get("ttiMs"),
        "ok": f"{'C' if b.get('counterOk') else '-'}{'T' if b.get('themeOk') else '-'}{'S' if b.get('searchOk') else '-'}",
    }
    rows.append(row)

with open(f"{OUT}/results.json", "w") as f:
    json.dump(rows, f, indent=2)

# ---- printed table ----
cols = [
    ("framework", "Framework", 13, "{}"),
    ("client_js_gz_kb", "JS gz KB", 9, "{}"),
    ("js_reqs", "JSreq", 6, "{}"),
    ("build_kb", "build KB", 9, "{}"),
    ("ssr_cards", "SSRcards", 9, "{}"),
    ("ttfb_ms", "TTFB ms", 8, "{}"),
    ("cold_ms", "cold ms", 8, "{}"),
    ("rps", "RPS", 8, "{}"),
    ("p99_ms", "p99 ms", 8, "{}"),
    ("tti_ms", "TTI ms", 7, "{}"),
    ("ok", "C/T/S", 6, "{}"),
]
hdr = "  ".join(h.ljust(w) for _, h, w, _ in cols)
print(hdr)
print("-" * len(hdr))
for r in rows:
    line = "  ".join(str(r.get(k) if r.get(k) is not None else "—").ljust(w) for k, _, w, _ in cols)
    print(line)
print()
print("C/T/S = Counter / Theme / Search interaction verified in a real browser")
print("client JS = gzipped (uniform level) sum of every JS resource + inline scripts the page loads")
