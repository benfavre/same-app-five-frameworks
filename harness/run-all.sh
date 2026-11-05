#!/usr/bin/env bash
# Compatibility entrypoint. Each invocation creates a fresh campaign.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "$ROOT/harness/run-benchmark.py" "$@"
