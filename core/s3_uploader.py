import os
import time

import boto3
import requests
from curl_cffi import requests as curl_requests

from core.logger import logger


class S3Uploader:
    def __init__(self):
        self.bucket = os.getenv('S3_BUCKET_NAME')
        self.region = os.getenv('AWS_REGION', 'ap-northeast-2')

        self._client = boto3.client('s3', region_name=self.region)
        
    def upload_from_url(self, image_url: str, s3_key: str, max_retries=3) -> str | None:
        """이미지 URL에서 다운로드 후 S3에 업로드 (재시도 로직 포함)"""
        if not image_url:
            return None
        # 무신사 이미지 CDN의 '//image.mss.kr/...' 형태 대응을 위한 https prefix 추가
        if image_url.startswith('//'):
            image_url = 'https:' + image_url

        for attempt in range(1, max_retries + 1):
            try:
                res = curl_requests.get(image_url, impersonate="chrome110", timeout=30)

                if res.status_code == 200:
                    content_type = res.headers.get('Content-Type', 'image/jpeg')
                    self._client.put_object(
                        Bucket=self.bucket,
                        Key=s3_key,
                        Body=res.content,
                        ContentType=content_type,
                    )
                    return s3_key
                else:
                    logger.warning(f"[S3 다운로드 실패] 상태코드 {res.status_code}: {image_url}")
                    return None

            except Exception as e:
                logger.warning(f"[S3 지연] {s3_key} 다운로드 {attempt}차 실패: {e}")

                if attempt == max_retries - 1:
                    logger.info("[우회] 일반 requests 라이브러리로 다운로드 방식을 우회합니다.")
                    try:
                        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                        res_fallback = requests.get(image_url, headers=headers, timeout=30)

                        if res_fallback.status_code == 200:
                            content_type = res_fallback.headers.get('Content-Type', 'image/jpeg')
                            self._client.put_object(
                                Bucket=self.bucket,
                                Key=s3_key,
                                Body=res_fallback.content,
                                ContentType=content_type,
                            )
                            return s3_key
                    except Exception as fallback_e:
                        logger.error(f"우회 시도를 실패했습니다: {fallback_e}")

                # 실패 시 2초간 대기 후 다음 시도
                time.sleep(2)

        logger.error(f"❌ [S3 업로드 최종 실패] {max_retries}회 재시도 초과: {s3_key}")
        return None