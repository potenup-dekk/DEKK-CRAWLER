#!/bin/bash
set -e

STATE_FILE="/app/data/crawler_state.json"

echo "[entrypoint] Playwright Chromium 브라우저 점검..."
python -m playwright install chromium

if [ ! -f "$STATE_FILE" ]; then
    echo "[entrypoint] 상태 파일 없음. 초기 대규모 수집을 시작합니다..."
    python /app/initial_load.py
    echo "[entrypoint] 초기 수집 완료. cron 시작."
else
    echo "[entrypoint] 상태 파일 확인됨. 바로 cron 시작."
fi

cron -f
