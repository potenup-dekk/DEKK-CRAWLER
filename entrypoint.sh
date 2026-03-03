#!/bin/bash
set -e

STATE_FILE="/app/data/crawler_state.json"
REQUIRED_PLATFORM_KEYS="${REQUIRED_PLATFORM_KEYS:-MUSINSA}"

echo "[entrypoint] Playwright Chromium 브라우저 점검..."
python -m playwright install chromium

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
    echo "[entrypoint] 상태 키 없음/비정상: ${MISSING_KEYS}. 초기 대규모 수집을 시작합니다..."
    python /app/initial_load.py
    echo "[entrypoint] 초기 수집 완료. cron 시작."
else
    echo "[entrypoint] 필수 상태 키 확인됨 (${REQUIRED_PLATFORM_KEYS}). 바로 cron 시작."
fi

cron -f
