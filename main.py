from datetime import datetime
from core.config import STATE_FILE_PATH
from core.state_manager import StateManager
from core.delivery import get_delivery
from core.pipeline import process_crawler
from core.logger import logger
from crawlers.musinsa import MusinsaCrawler

def main():
    logger.info("=== 크롤링 워커 실행을 시작합니다. ===")
    crawled_at = datetime.now().isoformat()
    state_manager = StateManager(STATE_FILE_PATH)
    delivery = get_delivery()

    active_crawlers = [MusinsaCrawler()]
    for crawler in active_crawlers:
        process_crawler(crawler, delivery, state_manager, crawled_at)

if __name__ == "__main__":
    main()
