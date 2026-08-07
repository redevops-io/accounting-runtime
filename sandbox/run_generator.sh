#!/usr/bin/env bash
# Host runner for the AI Accounting Runtime ground-truth generator.
# Posts invoices through the dedicated erpgen ERPNext sandbox and pulls the JSONL out.
#
#   ./run_generator.sh [COUNT]        # default 500
#
# Requires the erpgen sandbox up:  docker compose -p erpgen up -d   (see docker-compose.yml)
set -euo pipefail
COUNT="${1:-500}"
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/../data/ground-truth/gtc_pairs.jsonl"
mkdir -p "$(dirname "$OUT")"

docker cp "$HERE/generate_ground_truth.py" erpgen-backend-1:/tmp/generate_ground_truth.py
docker exec -e COUNT="$COUNT" -e OUT=/tmp/gtc_pairs.jsonl erpgen-backend-1 bash -lc \
  'cd /home/frappe/frappe-bench/sites && FRAPPE_SITE=frontend \
   /home/frappe/frappe-bench/env/bin/python /tmp/generate_ground_truth.py' \
  2>&1 | grep -E "GEN_OK|GEN_ERROR|GEN>"
docker cp erpgen-backend-1:/tmp/gtc_pairs.jsonl "$OUT"
echo "wrote $OUT ($(wc -l < "$OUT") records)"
