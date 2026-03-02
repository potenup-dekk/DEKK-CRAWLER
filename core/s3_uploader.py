import os
import time
from io import BytesIO

import boto3
import botocore
import requests
from curl_cffi import requests as curl_requests
from PIL import Image

from core.logger import logger


class S3Uploader:
    def __init__(self):
        self.bucket = os.getenv('S3_BUCKET_NAME')
        self.region = os.getenv('AWS_REGION')
        self._client = boto3.client('s3', region_name=self.region)

    def upload_from_url(self, image_url: str, s3_key: str, max_retries=3, target_size: tuple = None) -> str | None:
        """이미지 URL에서 다운로드 후 S3에 업로드. 성공 시 s3_key 반환, 실패 시 None."""
        if not image_url or not self.bucket:
            return None

        base_key = s3_key.rsplit('.', 1)[0]
        webp_s3_key = f"{base_key}.webp"
        
        if self._exists(webp_s3_key):
            logger.warning(f"[S3 스킵] 이미 존재하는 파일입니다: {webp_s3_key}")
            return webp_s3_key

        if image_url.startswith('//'):
            image_url = 'https:' + image_url

        raw_content = self._download(image_url, max_retries)
        if raw_content is None:
            logger.error(f"[S3 업로드 최종 실패] {max_retries}회 재시도 초과: {webp_s3_key}")
            return None

        resized_content = self._resize(raw_content, target_size)
        if resized_content is None:
            return None
        
        return self._put(webp_s3_key, resized_content)

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

    def _resize(self, content: bytes, target_size: tuple) -> bytes | None:
        """Pillow를 이용해 해상도를 350x525로 줄이고 WebP로 압축/변환."""
        try:
            img = Image.open(BytesIO(content))
            
            if target_size:
                img.thumbnail(target_size)
                
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
                
            output_buffer = BytesIO()
            img.save(output_buffer, format="WEBP", quality=80)
            
            return output_buffer.getvalue()
        except Exception as e:
            logger.error(f"[이미지 리사이징 에러]: {e}")
            return None
        
    def _put(self, s3_key: str, content: bytes) -> str | None:
        """S3에 파일 업로드."""
        try:
            self._client.put_object(
                Bucket=self.bucket,
                Key=s3_key,
                Body=content,
                ContentType='image/webp',
            )
            return s3_key
        except Exception as e:
            logger.error(f"[S3 PUT 실패] {s3_key}: {e}")
            return None
