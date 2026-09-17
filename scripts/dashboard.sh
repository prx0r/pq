#!/usr/bin/env bash
# dashboard.sh — boot the 0-9 transport in foreground (loopback only).
#   ./scripts/dashboard.sh [port]       # default 8791, token printed on stdout
# Remote access arrives via your Cloudflare tunnel, never 0.0.0.0.
source "$(dirname "$0")/lib.sh"
need python3
port="${1:-8791}"
cd "$PQ_ROOT"
DASH_PORT="$port" python3 dashboard/server.py
