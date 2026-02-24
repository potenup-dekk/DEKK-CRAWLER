import os
import json
import time
import requests
import boto3
from io import BytesIO

S3_BUCKET = os.getenv('S3_BUCKET_NAME', 'my-dekk-bucket')

s3_client = boto3.client(
    's3',
    region_name=os.getenv('AWS_REGION', 'ap-northeast-2'),
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
)

class S3Uploader:
    @staticmethod
    def upload_image_from_url(image_url, platform, date_str):
        if not image_url: return None
        try:
            response = requests.get(image_url, stream=True, timeout=10)
            response.raise_for_status()
            
            filename = image_url.split('/')[-1].split('?')[0] or f"{int(time.time())}.jpg"
            s3_key = f"cards/{platform}/{date_str}/{filename}"
            
            s3_client.upload_fileobj(
                BytesIO(response.content), 
                S3_BUCKET, 
                s3_key,
                ExtraArgs={'ContentType': 'image/jpeg'} 
            )
            return s3_key
        except Exception as e:
            print(f"❌ [S3 이미지 업로드 실패] {image_url}: {e}")
            return None

    @staticmethod
    def upload_raw_json(raw_data, platform, snap_id, date_str):
        s3_key = f"raw_data/{platform}/{date_str}/{snap_id}.json"
        try:
            s3_client.put_object(
                Bucket=S3_BUCKET,
                Key=s3_key,
                Body=json.dumps(raw_data, ensure_ascii=False),
                ContentType='application/json'
            )
            return s3_key
        except Exception as e:
            print(f"❌ [S3 JSON 업로드 실패] {snap_id}: {e}")
            return None