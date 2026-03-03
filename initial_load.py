import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from dotenv import load_dotenv

from core.backup_handler import backup_raw_data
from core.config import (CHUNK_SIZE, INITIAL_MAX_SCROLLS, MAX_WORKERS,
                         STATE_FILE_PATH)
from core.delivery import get_delivery
from core.logger import logger
from core.state_manager import StateManager
from crawlers.musinsa import MusinsaCrawler

load_dotenv()

def seed_initial_data():
    logger.info("[초기 세팅] 대규모 데이터 수집(병렬) 시작!")
    crawled_at = datetime.now().isoformat()
    crawler = MusinsaCrawler()
    delivery = get_delivery()
    
    state_manager = StateManager(STATE_FILE_PATH)

    platform = crawler.platform_name

    new_snap_ids = crawler.fetch_new_snaps(last_snap_id=None, max_scrolls=INITIAL_MAX_SCROLLS)
    total_snaps = len(new_snap_ids)
    logger.info(f"[{platform}] 총 {total_snaps}개의 스냅 수집 대상 확인 (병렬 처리 시작)")

    batch_raw_data_list = []
    successful_snap_ids = []
    scrape_error_msg = None
    completed_count = 0

    try:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_snap = {executor.submit(crawler.process_and_upload, snap_id): snap_id for snap_id in new_snap_ids}

            for future in as_completed(future_to_snap):
                snap_id = future_to_snap[future]
                completed_count += 1

                try:
                    raw_dict = future.result()
                    if raw_dict:
                        batch_raw_data_list.append(raw_dict)
                        successful_snap_ids.append(snap_id)

                    if completed_count % 100 == 0 or completed_count == total_snaps:
                        logger.info(f"병렬 수집 진행 중... ({completed_count}/{total_snaps})")

                except Exception as e:
                    scrape_error_msg = f"스냅 {snap_id} 수집 에러: {str(e)}"
                    logger.warning(scrape_error_msg)

    except Exception as e:
        scrape_error_msg = f"스레드 풀 실행 중 치명적 에러: {str(e)}"
        logger.error(scrape_error_msg, exc_info=True)

    if not batch_raw_data_list:
        logger.warning("수집된 데이터가 없습니다. 초기 세팅을 종료합니다.")
        return

    total_count = len(batch_raw_data_list)
    
    previous_last_id = state_manager.get_last_id(platform)

    if successful_snap_ids:
        latest_id = max(successful_snap_ids, key=int)
        state_manager.update_last_id(platform, latest_id)
        logger.info(f"[{platform}] 크롤링 완료. 상태 저장: {latest_id} (총 {total_count}개)")

    backup_raw_data(batch_raw_data_list, platform, crawled_at)

    logger.info(f"수집 완료. 총 {total_count}개 서버 전송 시작...")

    batch_id = None
    try:
        batch_id = delivery.create_batch(platform)

        for i in range(0, total_count, CHUNK_SIZE):
            chunk = batch_raw_data_list[i:i + CHUNK_SIZE]
            delivery.send_raw_data(batch_id, chunk, crawled_at)
            time.sleep(0.5)

        completed_at = datetime.now().isoformat()
        delivery.complete_batch(batch_id, total_count, completed_at, error_message=scrape_error_msg)
        
        logger.info(f"[{platform}] 초기 세팅 완료. API 전송 성공")

    except Exception as network_err:
        logger.error(f"네트워크 전송 중 치명적 에러 발생: {network_err}", exc_info=True)
        state_manager.update_last_id(platform, previous_last_id)
        logger.warning(f"[{platform}] API 전송 실패로 상태 롤백 완료: {previous_last_id}")
        logger.warning(f"[{platform}] 다음 실행에서 동일 스냅을 다시 수집/전송합니다. (이미지 S3는 중복 업로드 스킵)")
        if batch_id:
            completed_at = datetime.now().isoformat()
            err_msg = scrape_error_msg or str(network_err)
            delivery.complete_batch(batch_id, total_count, completed_at, error_message=err_msg)

if __name__ == "__main__":
    seed_initial_data()