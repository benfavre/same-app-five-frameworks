#!/usr/bin/env bash
# Head-to-head orchestrator. For each app: cold-start, TTFB (warm median),
# RPS/p99 (oha), and browser client-JS/TTI/interaction checks. Node apps are
# started/stopped by killing the actual port LISTENER (npx/node grandchildren
# don't die with their parent, so we kill by port). bext is started and
# measured the same way (its own process, cold start = spawn to first 200).
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APPS=$ROOT/apps
OUT=$ROOT/results
MEASURE="node $ROOT/harness/h2h-measure.mjs"
DUR=8s; CONC=50
mkdir -p "$OUT"

free_port(){ local port=$1 sig pids
  for sig in TERM TERM KILL; do
    pids=$(ss -ltnpH "sport = :$port" 2>/dev/null | grep -oE 'pid=[0-9]+' | cut -d= -f2 | sort -u)
    [ -z "$pids" ] && return 0
    kill -$sig $pids 2>/dev/null; sleep 0.5
  done
}
wait_ready(){ local url=$1; for i in $(seq 1 240); do [ "$(curl -s -o /dev/null -w '%{http_code}' "$url" 2>/dev/null)" = 200 ] && return 0; sleep 0.1; done; return 1; }
ttfb_median(){ local url=$1; { for i in $(seq 1 50); do curl -s -o /dev/null -w '%{time_starttransfer}\n' "$url"; done; } | sort -n | awk '{a[NR]=$1} END{printf "%.2f", a[int(NR/2)+1]*1000}'; }
# Every load request carries a unique ?r= query (all frameworks alike). The Node
# apps ignore it; for bext it defeats the render-result cache, which can promote
# a page after two byte-identical renders: under load two renders land in the same
# millisecond, look identical, and the page is then replayed instead of rendered.
# (oha's --rand-regex-url drops keep-alive and mangles hostnames, so the unique
# URLs come from a file: a million of them, more than one run can consume.)
urls_file(){ local f; f=$(mktemp); awk -v u="$1" 'BEGIN{for(i=0;i<1000000;i++) print u "?r=" i}' > "$f"; echo "$f"; }
oha_json(){ local f; f=$(urls_file "$1")
  oha -z $DUR -c $CONC --no-tui --output-format json --urls-from-file "$f" 2>/dev/null > "$2"; rm -f "$f"; }
stamp(){ curl -s "$1" | grep -o 'data-rendered-at="[0-9]*"' | head -1 | tr -dc '0-9'; echo; }
# Uncached proof, two parts. Idle: two renders ~1s apart must differ. Under load:
# 20 responses sampled while oha runs must carry 20 distinct timestamps (a cache
# that only kicks in under concurrency is invisible to the idle check).
proof(){ local url=$1 outf=$2 r1 r2 s n op
  r1=$(stamp "$url"); sleep 1.1; r2=$(stamp "$url")
  local f; f=$(urls_file "$url")
  oha -z 4s -c $CONC --no-tui --urls-from-file "$f" >/dev/null 2>&1 &
  op=$!; sleep 1
  s=$(for i in $(seq 1 20); do stamp "${url}?r=p$RANDOM$i"; sleep 0.1; done)
  wait $op; rm -f "$f"
  n=$(printf '%s\n' $s | sort -u | grep -c .)
  echo "{\"r1\":\"$r1\",\"r2\":\"$r2\",\"loadDistinct\":$n,\"loadSamples\":20,\"uncached\":$([ -n "$r1" ] && [ "$r1" != "$r2" ] && [ "$n" = 20 ] && echo true || echo false)}" > "$outf"
  echo "    proof: $(cat "$outf")"
}

cold_node(){ # dir start port outfile -> min of 2 spawns (ms)
  local dir=$1 start=$2 port=$3 outf=$4 best=999999 t0 t1 ms
  for k in 1 2; do
    free_port "$port"
    ( cd "$dir" && eval "$start" >/tmp/h2h-cold.log 2>&1 ) &
    t0=$(date +%s.%N)
    for i in $(seq 1 600); do [ "$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$port/" 2>/dev/null)" = 200 ] && break; sleep 0.025; done
    t1=$(date +%s.%N)
    ms=$(awk "BEGIN{printf \"%.0f\", ($t1-$t0)*1000}")
    free_port "$port"
    [ "$ms" -lt "$best" ] 2>/dev/null && best=$ms
  done
  echo "$best" > "$outf"
}

run_node(){ # fw
  local fw=$1 dir port start
  dir=$APPS/$fw
  port=$(python3 -c "import json;print(json.load(open('$dir/bench.json'))['port'])")
  start=$(python3 -c "import json;print(json.load(open('$dir/bench.json'))['start'])")
  echo ">>> $fw (port $port)"
  echo "    cold-start..."; cold_node "$dir" "$start" "$port" "$OUT/$fw.cold"
  echo "    starting persistent server..."; free_port "$port"
  ( cd "$dir" && eval "$start" >/tmp/h2h-$fw.log 2>&1 ) &
  if ! wait_ready "http://127.0.0.1:$port/"; then echo "    !! $fw never became ready (see /tmp/h2h-$fw.log)"; free_port "$port"; return; fi
  proof "http://127.0.0.1:$port/" "$OUT/$fw.proof"
  echo "    ttfb..."; ttfb_median "http://127.0.0.1:$port/" > "$OUT/$fw.ttfb"
  echo "    load (oha $DUR c$CONC)..."; oha_json "http://127.0.0.1:$port/" "$OUT/$fw.oha.json"
  echo "    browser..."; $MEASURE "http://127.0.0.1:$port/" "$fw" 2>/dev/null | tail -1 > "$OUT/$fw.browser.json"
  free_port "$port"
  echo "    done $fw"
}

for fw in next remix astro qwik; do run_node "$fw"; done
# bext runs as its own process exactly like the Node apps (start command in
# apps/bext/bench.json): the bext binary (BEXT_BIN, default `bext-server` on PATH)
# plus its shared framework (BEXT_SHARED_FRAMEWORK_DIR, or a system install).
if command -v "${BEXT_BIN:-bext-server}" >/dev/null 2>&1 && { [ -d "${BEXT_SHARED_FRAMEWORK_DIR:-/usr/share/bext/framework}" ]; }; then
  export BEXT_SHARED_FRAMEWORK_DIR="${BEXT_SHARED_FRAMEWORK_DIR:-/usr/share/bext/framework}"
  run_node bext
else
  echo ">>> bext SKIPPED — needs BEXT_BIN (or bext-server on PATH) and BEXT_SHARED_FRAMEWORK_DIR (see README)"
fi
echo "ALL DONE -> $OUT"
