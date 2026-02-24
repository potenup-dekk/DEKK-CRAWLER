import os
import time
from datetime import datetime
from core.state_manager import StateManager
from core.delivery import send_to_sqs, send_to_batch_api
from crawlers.musinsa import MusinsaCrawler

def main():
    print(f"\n🚀 [{datetime.now()}] 크롤링 워커 실행을 시작합니다.")
    today_str = datetime.now().strftime('%Y/%m/%d')
    state_manager = StateManager('/app/data/crawler_state.json')
    
    active_crawlers = [
        MusinsaCrawler()
    ]
    
    all_processed_dtos = []
    
    for crawler in active_crawlers:
        platform = crawler.platform_name
        last_id = state_manager.get_last_id(platform)
        
        new_snap_ids = crawler.fetch_new_snaps(last_id)
        print(f"총 {len(new_snap_ids)}개의 신규 스냅을 처리합니다.")
        
        for snap_id in new_snap_ids:
            try:
                dto = crawler.process_and_upload(snap_id, today_str)
                all_processed_dtos.append(dto)
                
                state_manager.update_last_id(platform, snap_id)
                time.sleep(1) # 차단 방지 매너 딜레이
            except Exception as e:
                print(f"❌ {platform} 스냅({snap_id}) 처리 에러: {e}")

    if all_processed_dtos:
        delivery_mode = os.getenv('DELIVERY_MODE', 'SQS').upper()
        print(f"\n📦 데이터 수집 완료. [{delivery_mode}] 방식으로 전송을 시작합니다...")
        
        if delivery_mode == 'BATCH':
            send_to_batch_api(all_processed_dtos)
        elif delivery_mode == 'SQS':
            send_to_sqs(all_processed_dtos)
        else:
            print(f"❌ 알 수 없는 DELIVERY_MODE: {delivery_mode}")

if __name__ == "__main__":
    main()