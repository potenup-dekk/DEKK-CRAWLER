import os
import requests
from .base import BaseDelivery


class BatchDelivery(BaseDelivery):
    def __init__(self):
        self.url = os.getenv('SPRING_BATCH_API_URL')

    def send(self, dtos: list) -> None:
        if not dtos:
            return
        try:
            res = requests.post(
                self.url,
                headers={'Content-Type': 'application/json'},
                json=dtos,
                timeout=30
            )
            res.raise_for_status()
            print(f"✅ [Batch API 전송 완료] {len(dtos)}개 데이터 DB 반영.")
        except Exception as e:
            print(f"❌ [Batch API 전송 실패]: {e}")
