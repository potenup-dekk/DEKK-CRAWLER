from core.logger import logger
from core.s3_uploader import S3Uploader


def backup_raw_data(batch_raw_data_list: list, platform: str, crawled_at: str) -> bool:
    """
    수집한 데이터에서 원본을 추출하여 S3에 백업
    
    Args:
        batch_raw_data_list: 처리된 크롤링 데이터 리스트 (각 항목은 _original_raw_data 필드 포함 가능)
        platform: 플랫폼명 (예: 'MUSINSA')
        crawled_at: 크롤링 시각 (ISO format, ':' 포함)
    
    Returns:
        bool: 백업 성공 여부
    """
    if not batch_raw_data_list:
        logger.warning(f"[{platform}] 백업할 데이터가 없습니다.")
        return False
    
    original_data_list = []
    for item in batch_raw_data_list:
        if '_original_raw_data' in item:
            original_data_list.append(item.pop('_original_raw_data'))
        else:
            # 혹시 원본 필드가 없으면 현재 데이터를 백업
            original_data_list.append(item.copy())
    
    safe_crawled_at = crawled_at.replace(':', '-')
    backup_key = f"backups/raw-data/{platform.lower()}/original_{safe_crawled_at}_{len(original_data_list)}.json"
    
    backup_s3_key = S3Uploader().upload_json_backup(original_data_list, backup_key)
    
    if backup_s3_key:
        logger.info(f"[{platform}] 원본 데이터 S3 백업 완료: {backup_s3_key}")
        return True
    else:
        logger.warning(f"[{platform}] 원본 데이터 S3 백업 실패 (배치 전송은 계속 진행)")
        return False
