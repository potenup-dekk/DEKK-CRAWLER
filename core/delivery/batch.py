import json
import logging
import os

import requests
from requests import ConnectionError, HTTPError, Timeout
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential, before_sleep_log

from core.logger import logger

from .base import BaseDelivery


def _is_transient(exc: BaseException) -> bool:
    """5xx 서버 오류 및 네트워크 오류만 재시도. 4xx 클라이언트 오류는 즉시 실패."""
    if isinstance(exc, HTTPError):
        return exc.response is not None and exc.response.status_code >= 500
    return isinstance(exc, (ConnectionError, Timeout))


def _log_final_error(retry_state):
    logger.error(
        "[최종 실패] %s 3회 모두 실패: %s",
        retry_state.fn.__name__,
        retry_state.outcome.exception(),
    )
    raise retry_state.outcome.exception()


_SEND_RETRY_KWARGS = dict(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception(_is_transient),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    retry_error_callback=_log_final_error,
)


class BatchDelivery(BaseDelivery):
    def __init__(self):
        self.url = os.getenv('BATCH_API_URL')

    def create_batch(self, platform: str) -> int:
        """배치 생성은 POST 비멱등 — 재시도 시 고아 배치 생성 위험으로 fail-fast."""
        url = f"{self.url}/batches"
        res = requests.post(url, json={"platform": platform}, timeout=10)
        res.raise_for_status()
        batch_id = res.json().get('data', {}).get('batchId')
        if batch_id is None:
            raise ValueError(f"응답에 batchId 없음: {res.text}")
        logger.info("[배치 생성 완료] Platform: %s, Batch ID: %s", platform, batch_id)
        return batch_id

    @retry(**_SEND_RETRY_KWARGS)
    def send_raw_data(self, batch_id: int, chunk_list: list, crawled_at: str):
        url = f"{self.url}/batches/{batch_id}/raw-data"
        payload = {
            "rawData": json.dumps(chunk_list, ensure_ascii=False),
            "crawledAt": crawled_at
        }
        res = requests.post(url, json=payload, timeout=30)
        res.raise_for_status()
        logger.info("[청크 전송 완료] Batch ID: %s, %s개 데이터 전송", batch_id, len(chunk_list))

    def complete_batch(self, batch_id: int, total_count: int, completed_at: str, error_message: str = None):
        """배치 완료 신호는 멱등성 보장 불가 — 재시도 시 중복 완료 위험으로 fail-fast."""
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
