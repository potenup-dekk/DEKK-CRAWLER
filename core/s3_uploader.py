import os
import time

import boto3
import botocore
import requests
from curl_cffi import requests as curl_requests

from core.logger import logger


class S3Uploader:
    def __init__(self):
        self.bucket = os.getenv('S3_BUCKET_NAME', 'musinsa-crawler-bucket')
        self.region = os.getenv('AWS_REGION', 'ap-northeast-2')
        self._client = boto3.client('s3', region_name=self.region)

    def upload_from_url(self, image_url: str, s3_key: str, max_retries=3) -> str | None:
        """이미지 URL에서 다운로드 후 S3에 업로드. 성공 시 s3_key 반환, 실패 시 None."""
        if not image_url or not self.bucket:
            return None

        if self._exists(s3_key):
            logger.warning(f"[S3 스킵] 이미 존재하는 파일입니다: {s3_key}")
            return s3_key

        if image_url.startswith('//'):
            image_url = 'https:' + image_url

        content = self._download(image_url, max_retries)
        if content is None:
            logger.error(f"[S3 업로드 최종 실패] {max_retries}회 재시도 초과: {s3_key}")
            return None

        return self._put(s3_key, content)

    def _exists(self, s3_key: str) -> bool:
        """S3에 이미 존재하는 파일인지 확인."""
        try:
            self._client.head_object(Bucket=self.bucket, Key=s3_key)
            return True
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] != '404':
                logger.error(f"[S3 중복 검사 에러] {s3_key}: {e}")
            return False
        except Exception as e:
            logger.warning(f"[S3 중복 검사 실패] {s3_key}: {e}")
            return False

    def _download(self, image_url: str, max_retries: int) -> bytes | None:
        """curl_cffi로 이미지 다운로드. 실패 시 requests로 우회."""
        for attempt in range(1, max_retries + 1):
            try:
                res = curl_requests.get(image_url, impersonate='chrome110', timeout=30)
                if res.status_code == 200:
                    return res.content
                logger.warning(f"[S3 다운로드 실패] 상태코드 {res.status_code}: {image_url}")
                return None
            except Exception as e:
                logger.warning(f"[S3 지연] {image_url} 다운로드 {attempt}차 실패: {e}")
                if attempt < max_retries:
                    time.sleep(2)

        return self._download_fallback(image_url)

    def _download_fallback(self, image_url: str) -> bytes | None:
        """curl_cffi 실패 시 일반 requests로 재시도."""
        logger.info("[우회] 일반 requests 라이브러리로 다운로드 방식을 우회합니다.")
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            res = requests.get(image_url, headers=headers, timeout=30)
            if res.status_code == 200:
                return res.content
        except Exception as e:
            logger.error(f"우회 시도를 실패했습니다: {e}")
        return None

    def _put(self, s3_key: str, content: bytes) -> str | None:
        """S3에 파일 업로드."""
        try:
            self._client.put_object(
                Bucket=self.bucket,
                Key=s3_key,
                Body=content,
                ContentType='image/jpeg',
            )
            return s3_key
        except Exception as e:
            logger.error(f"[S3 PUT 실패] {s3_key}: {e}")
            return None
