import os
import subprocess
from datetime import datetime

from dotenv import load_dotenv

from core.config import STATE_FILE_PATH
from core.delivery import get_delivery
from core.logger import logger
from core.pipeline import process_crawler
from core.state_manager import StateManager
from crawlers.musinsa import MusinsaCrawler

load_dotenv('/app/.env')

def main():
    logger.info("[사전점검] Playwright Chromium 설치 확인...")
    try:
        subprocess.run(["python", "-m", "playwright", "install", "chromium"], 
                      check=True, capture_output=True, timeout=60)
        logger.info("[사전점검] Playwright Chromium 설치 완료")
    except Exception as e:
        logger.error(f"[사전점검] Playwright 설치 실패: {e}")
        raise
    
    logger.info("=== 크롤링 워커 실행을 시작합니다. ===")
    crawled_at = datetime.now().isoformat()
    state_manager = StateManager(STATE_FILE_PATH)
    delivery = get_delivery()

    active_crawlers = [MusinsaCrawler()]
    for crawler in active_crawlers:
        process_crawler(crawler, delivery, state_manager, crawled_at)

if __name__ == "__main__":
    main()
