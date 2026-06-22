#!/usr/bin/env bash
# Head-to-head orchestrator. For each app: cold-start, TTFB (warm median),
# RPS/p99 (oha), and browser client-JS/TTI/interaction checks. Node apps are
# started/stopped by killing the actual port LISTENER (npx/node grandchildren
# don't die with their parent, so we kill by port). bext is the always-on
# masquerade (its "cold" = first request on an un-compiled route after a purge).
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APPS=$ROOT/apps
OUT=$ROOT/results
MEASURE="node $ROOT/harness/h2h-measure.mjs"
DUR=8s; CONC=50
# bext entry needs the bext runtime serving the app at BEXT_URL (see README).
# The four Node apps run out of the box; the bext step is skipped if unreachable.
BEXT_URL="${BEXT_URL:-http://h2h-bext.local/}"
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
oha_json(){ oha -z $DUR -c $CONC --no-tui --output-format json "$1" 2>/dev/null > "$2"; }

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
  local fw=$1 dir=$APPS/$fw port start
  port=$(python3 -c "import json;print(json.load(open('$dir/bench.json'))['port'])")
  start=$(python3 -c "import json;print(json.load(open('$dir/bench.json'))['start'])")
  echo ">>> $fw (port $port)"
  echo "    cold-start..."; cold_node "$dir" "$start" "$port" "$OUT/$fw.cold"
  echo "    starting persistent server..."; free_port "$port"
  ( cd "$dir" && eval "$start" >/tmp/h2h-$fw.log 2>&1 ) &
  if ! wait_ready "http://127.0.0.1:$port/"; then echo "    !! $fw never became ready (see /tmp/h2h-$fw.log)"; free_port "$port"; return; fi
  # uncached proof: two renders ~1s apart must differ (per-request render, not cached/prerendered)
  local r1 r2; r1=$(curl -s "http://127.0.0.1:$port/" | grep -o 'data-rendered-at="[0-9]*"' | head -1); sleep 1.1; r2=$(curl -s "http://127.0.0.1:$port/" | grep -o 'data-rendered-at="[0-9]*"' | head -1)
  echo "{\"r1\":\"$r1\",\"r2\":\"$r2\",\"uncached\":$([ -n "$r1" ] && [ "$r1" != "$r2" ] && echo true || echo false)}" > "$OUT/$fw.proof"
  echo "    proof: $r1 vs $r2"
  echo "    ttfb..."; ttfb_median "http://127.0.0.1:$port/" > "$OUT/$fw.ttfb"
  echo "    load (oha $DUR c$CONC)..."; oha_json "http://127.0.0.1:$port/" "$OUT/$fw.oha.json"
  echo "    browser..."; $MEASURE "http://127.0.0.1:$port/" "$fw" 2>/dev/null | tail -1 > "$OUT/$fw.browser.json"
  free_port "$port"
  echo "    done $fw"
}

run_bext(){
  local url="$BEXT_URL" p t0 t1
  if [ "$(curl -s -o /dev/null -w '%{http_code}' "$url" 2>/dev/null)" != 200 ]; then
    echo ">>> bext SKIPPED — $url unreachable (needs the bext runtime; see README)"; return
  fi
  echo ">>> bext (masquerade, always-on)"
  p=$(cat /run/bext/cache-purge.port 2>/dev/null || cat /tmp/bext-cache-purge.port 2>/dev/null)
  curl -s -X POST "http://127.0.0.1:$p/nginx-cache/purge-site" -H 'Content-Type: application/json' -d '{"host":"h2h-bext.local"}' >/dev/null
  sleep 0.5
  t0=$(date +%s.%N); curl -s -o /dev/null "$url"; t1=$(date +%s.%N)
  awk "BEGIN{printf \"%.0f\", ($t1-$t0)*1000}" > "$OUT/bext.cold"
  echo "    ttfb..."; ttfb_median "$url" > "$OUT/bext.ttfb"
  echo "    load (oha $DUR c$CONC)..."; oha_json "$url" "$OUT/bext.oha.json"
  echo "    browser..."; $MEASURE "$url" "bext" 2>/dev/null | tail -1 > "$OUT/bext.browser.json"
  echo "    done bext"
}

for fw in next remix astro qwik; do run_node "$fw"; done
run_bext
echo "ALL DONE -> $OUT"
