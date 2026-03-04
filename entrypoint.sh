#!/bin/bash
set -e

STATE_FILE="/app/data/crawler_state.json"
REQUIRED_PLATFORM_KEYS="${REQUIRED_PLATFORM_KEYS:-MUSINSA}"
ENV_FILE="/opt/crawler/.env"

echo "[entrypoint] .env 로드..."
if [ -f "$ENV_FILE" ]; then
    export $(grep -v '^#' "$ENV_FILE" | xargs)
fi

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
    python /app/initial_load.py
fi

echo "[entrypoint] crontab 생성..."

cat <<EOF > /tmp/crontab_with_env
*/10 * * * * . ${ENV_FILE} && cd /app && /usr/bin/python3 main.py >> /proc/1/fd/1 2>> /proc/1/fd/2
EOF

cat /tmp/crontab_with_env

crontab /tmp/crontab_with_env

echo "[entrypoint] cron 시작..."
cron -f
