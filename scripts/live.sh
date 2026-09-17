#!/usr/bin/env bash
# live.sh — live red-team run with a real model. SPENDS inference budget.
#   ./scripts/live.sh [max_turns]        # default 20, backend $PQ_MODEL or muse-spark
#   PQ_SPEND_CAP_TOKENS=500 ./scripts/live.sh
source "$(dirname "$0")/lib.sh"
need python3
turns="${1:-20}"
echo "live run: backend=${PQ_MODEL:-muse-spark-1.3-contributor} turns=$turns (spends budget)"
cd "$PQ_ROOT"
python3 harness.py "$turns" 2>&1 | tee "$RUNS/live-$(run_id).log"
