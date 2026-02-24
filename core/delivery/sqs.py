import os
import json
import uuid
import boto3
from .base import BaseDelivery


class SQSDelivery(BaseDelivery):
    def __init__(self):
        self.client = boto3.client(
            'sqs',
            region_name=os.getenv('AWS_REGION', 'ap-northeast-2'),
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
        )
        self.queue_url = os.getenv('SQS_QUEUE_URL')

    def send(self, dtos: list) -> None:
        if not dtos:
            return

        chunks = [dtos[i:i + 10] for i in range(0, len(dtos), 10)]
        total_success = 0

        for chunk in chunks:
            entries = [
                {'Id': str(uuid.uuid4()), 'MessageBody': json.dumps(dto, ensure_ascii=False)}
                for dto in chunk
            ]
            try:
                response = self.client.send_message_batch(QueueUrl=self.queue_url, Entries=entries)
                total_success += len(response.get('Successful', []))

                failed = response.get('Failed', [])
                if failed:
                    failed_ids = {f['Id'] for f in failed}
                    retry_entries = [e for e in entries if e['Id'] in failed_ids]
                    retry = self.client.send_message_batch(QueueUrl=self.queue_url, Entries=retry_entries)
                    total_success += len(retry.get('Successful', []))
                    if retry.get('Failed'):
                        print(f"❌ [SQS 재시도 후에도 실패]: {retry['Failed']}")
            except Exception as e:
                print(f"❌ [SQS 전송 실패]: {e}")

        print(f"✅ [SQS 전송 완료] {total_success}/{len(dtos)}개 큐 삽입.")
