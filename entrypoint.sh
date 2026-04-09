#!/bin/bash
set -e

STATE_FILE="/app/data/crawler_state.json"
REQUIRED_PLATFORM_KEYS="${REQUIRED_PLATFORM_KEYS:-MUSINSA}"
AWS_REGION="${AWS_REGION:-ap-northeast-2}"

echo "[entrypoint] Playwright Chromium 점검..."
python -m playwright install chromium

# 상태 체크
CHECK_RESULT=$(python - <<PY
import json
import os

state_file = "${STATE_FILE}"
required_keys = [k.strip() for k in "${REQUIRED_PLATFORM_KEYS}".split(",") if k.strip()]

if not os.path.exists(state_file):
    print("true|" + ",".join(required_keys))
else:
    try:
        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)
        missing = [k for k in required_keys if not state.get(k)]
        if missing:
            print("true|" + ",".join(missing))
        else:
            print("false|")
    except Exception:
        print("true|" + ",".join(required_keys))
PY
)

NEED_INITIAL_LOAD="${CHECK_RESULT%%|*}"
MISSING_KEYS="${CHECK_RESULT#*|}"

if [ "$NEED_INITIAL_LOAD" = "true" ]; then
    echo "[entrypoint] 초기 수집 실행..."
    python /app/batch/initial_load.py
fi

echo "[entrypoint] crontab 등록..."
crontab /app/crontab

echo "[DEBUG] 등록된 crontab:"
crontab -l
echo "---"

echo "[entrypoint] cron 시작..."
cron -f
