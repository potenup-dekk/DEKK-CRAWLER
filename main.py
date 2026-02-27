from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from core.config import STATE_FILE_PATH
from core.state_manager import StateManager
from core.delivery import get_delivery
from crawlers.musinsa import MusinsaCrawler
from core.logger import logger

CHUNK_SIZE = 20

def main():
    logger.info("=== 크롤링 워커 실행을 시작합니다. ===")
    crawled_at = datetime.now().isoformat()
    state_manager = StateManager(STATE_FILE_PATH)
    
    active_crawlers = [MusinsaCrawler()]
    delivery = get_delivery()

    for crawler in active_crawlers:
        platform = crawler.platform_name
        last_id = state_manager.get_last_id(platform)
        new_snap_ids = crawler.fetch_new_snaps(last_id)

        if not new_snap_ids:
            logger.info(f"[{platform}] 새로운 스냅이 없습니다.")
            continue

        logger.info(f"[{platform}] 총 {len(new_snap_ids)}개의 신규 스냅 처리 (병렬)")

        batch_raw_data_list = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_snap = {executor.submit(crawler.process_and_upload, snap_id): snap_id for snap_id in new_snap_ids}

            for future in as_completed(future_to_snap):
                snap_id = future_to_snap[future]
                try:
                    raw_dict = future.result()
                    if raw_dict:
                        batch_raw_data_list.append(raw_dict)
                except Exception as e:
                    logger.error(f"[{platform}] 스냅({snap_id}) 처리 에러: {e}", exc_info=True)
    
        if not batch_raw_data_list:
            continue

        logger.info(f"[{platform}] {len(batch_raw_data_list)}개 수집 완료. 전송 시작...")

        batch_id = None
        try:
            batch_id = delivery.create_batch(platform)

            for i in range(0, len(batch_raw_data_list), CHUNK_SIZE):
                chunk = batch_raw_data_list[i:i + CHUNK_SIZE]
                delivery.send_raw_data(batch_id, chunk, crawled_at)

            completed_at = datetime.now().isoformat()
            delivery.complete_batch(batch_id, len(batch_raw_data_list), completed_at)
            
            # 병렬 처리 시 완료 순서가 섞이므로, 원본 리스트의 맨 마지막 ID(가장 최신)를 저장
            latest_id_to_update = new_snap_ids[-1]
            state_manager.update_last_id(platform, latest_id_to_update)
            logger.info(f"[{platform}] 마지막 수집 ID 갱신 완료: {latest_id_to_update}")
            
        except Exception as e:
            logger.error(f"[{platform}] 전송 실패. 다음 크론에서 재시도합니다. 오류: {e}", exc_info=True)
            if batch_id:
                completed_at = datetime.now().isoformat()
                delivery.complete_batch(batch_id, len(batch_raw_data_list), completed_at, error_message=str(e))

if __name__ == "__main__":
    main()
