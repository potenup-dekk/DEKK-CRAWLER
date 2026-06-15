import json
import os

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log
import logging

from core.logger import logger

from .base import BaseDelivery

_RETRY_KWARGS = dict(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


class BatchDelivery(BaseDelivery):
    def __init__(self):
        self.url = os.getenv('BATCH_API_URL')

    @retry(**_RETRY_KWARGS)
    def create_batch(self, platform: str) -> int:
        url = f"{self.url}/batches"
        res = requests.post(url, json={"platform": platform}, timeout=10)
        res.raise_for_status()
        batch_id = res.json().get('data', {}).get('batchId')
        logger.info("[배치 생성 완료] Platform: %s, Batch ID: %s", platform, batch_id)
        return batch_id

    @retry(**_RETRY_KWARGS)
    def send_raw_data(self, batch_id: int, chunk_list: list, crawled_at: str):
        url = f"{self.url}/batches/{batch_id}/raw-data"
        payload = {
            "rawData": json.dumps(chunk_list, ensure_ascii=False),
            "crawledAt": crawled_at
        }
        res = requests.post(url, json=payload, timeout=30)
        res.raise_for_status()
        logger.info("[청크 전송 완료] Batch ID: %s, %s개 데이터 전송", batch_id, len(chunk_list))

    @retry(**_RETRY_KWARGS)
    def complete_batch(self, batch_id: int, total_count: int, completed_at: str, error_message: str = None):
        url = f"{self.url}/batches/{batch_id}/complete"
        payload = {
            "totalCount": total_count,
            "completedAt": completed_at,
            "errorMessage": error_message
        }
        res = requests.post(url, json=payload, timeout=10)
        res.raise_for_status()
        if error_message:
            logger.warning("[배치 종료 (에러포함)] Batch ID: %s, Total: %s", batch_id, total_count)
        else:
            logger.info("[배치 종료 (성공)] Batch ID: %s, Total: %s개 수집 완료!", batch_id, total_count)
