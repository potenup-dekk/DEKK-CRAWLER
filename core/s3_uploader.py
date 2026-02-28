import os

import boto3
from curl_cffi import requests as curl_requests

from core.logger import logger


class S3Uploader:
    def __init__(self):
        self.bucket = os.getenv('S3_BUCKET_NAME')
        self.region = os.getenv('AWS_REGION', 'ap-northeast-2')
        
        self._client = boto3.client('s3', region_name=self.region)

    def upload_from_url(self, image_url: str, s3_key: str) -> str | None:
        """이미지 URL에서 다운로드 후 S3에 업로드. 성공 시 S3 key 반환."""
        if not image_url:
            return None

        # 무신사 이미지 CDN의 '//image.mss.kr/...' 형태 대응을 위한 https prefix 추가
        if image_url.startswith('//'):
            image_url = 'https:' + image_url

        try:
            # 방화벽 차단을 피하기 위해 브라우저 위장 다운로드
            res = curl_requests.get(image_url, impersonate="chrome110", timeout=10)
            
            if res.status_code != 200:
                logger.warning(f"[S3 다운로드 실패] 상태코드 {res.status_code}: {image_url}")
                return None

            content_type = res.headers.get('Content-Type', 'image/jpeg')
            
            self._client.put_object(
                Bucket=self.bucket,
                Key=s3_key,
                Body=res.content,
                ContentType=content_type,
            )
            
            return s3_key
            
        except Exception as e:
            logger.error(f"[S3 업로드 에러] {s3_key}: {e}", exc_info=True)
            return None
        