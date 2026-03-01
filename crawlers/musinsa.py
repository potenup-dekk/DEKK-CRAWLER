import json
import random
import time
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests
from playwright.sync_api import sync_playwright

from core.logger import logger
from core.s3_uploader import S3Uploader

from .base import BaseCrawler


def _get_filename(url: str) -> str:
    name = urlparse(url).path.split('/')[-1]
    return name if name else 'image.jpg'


class MusinsaCrawler(BaseCrawler):
    platform_name = "MUSINSA"

    def __init__(self):
        self.s3 = S3Uploader()

    def fetch_new_snaps(self, last_snap_id, max_scrolls=5):
        """Playwright로 스크롤하며 last_snap_id 이전까지의 신규 스냅 ID만 추출 (Delta Crawling)"""
        logger.info(f"[{self.platform_name}] 신규 스냅 탐색 시작 (마지막 ID: {last_snap_id})")

        new_ids = []
        seen = set()

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                ]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={'width': 1920, 'height': 1080},
            )
            page = context.new_page()
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            page.goto("https://www.musinsa.com/snap/main/recommend?gf=A&sort=NEWEST")

            try:
                page.wait_for_selector("a[href*='/snap/']", timeout=10000)
            except Exception as e:
                logger.error(f"페이지 로딩 또는 봇 차단 발생: {e}")
                browser.close()
                return []

            found_last = False
            for _ in range(max_scrolls):
                for link in page.locator("a[href*='/snap/']").all():
                    href = link.get_attribute("href")
                    if not href:
                        continue
                    snap_id = href.split('/snap/')[-1].split('?')[0]
                    if not snap_id.isdigit():
                        continue
                    if snap_id == last_snap_id:
                        found_last = True
                        break
                    if snap_id not in seen:
                        seen.add(snap_id)
                        new_ids.append(snap_id)

                if found_last:
                    break

                page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(1.5, 3.0))

            browser.close()

        logger.info(f"[{self.platform_name}] 스냅 탐색 완료: {len(new_ids)}개 발견")
        return new_ids[::-1]

    def process_and_upload(self, snap_id):
        time.sleep(random.uniform(1.5, 3.5))  # 방화벽 회피 - 꼭 유지

        response = self._fetch_snap_html(snap_id)
        raw_snap_data = self._parse_snap_data(snap_id, response)

        goods_nos = [str(g.get('goodsNo')) for g in raw_snap_data.get('goods', []) if g.get('goodsNo')]
        raw_snap_data['goods_detail_list'] = self._fetch_goods_batch(goods_nos)

        self._upload_images_to_s3(snap_id, raw_snap_data)
        return raw_snap_data

    def _fetch_snap_html(self, snap_id):
        url = f"https://www.musinsa.com/snap/{snap_id}"
        try:
            return curl_requests.get(url, impersonate="chrome110", timeout=15)
        except Exception as e:
            logger.error(f"스냅 {snap_id} 네트워크 요청 실패: {e}")
            raise Exception("네트워크 에러")

    def _parse_snap_data(self, snap_id, response) -> dict:
        soup = BeautifulSoup(response.text, 'html.parser')
        script_tag = soup.find('script', id='__NEXT_DATA__')

        if not script_tag:
            logger.error(f"스냅 {snap_id} NEXT_DATA 없음. 상태코드: {response.status_code}")
            raise Exception("NEXT_DATA 파싱 실패")

        queries = (
            json.loads(script_tag.string)
            .get('props', {})
            .get('pageProps', {})
            .get('dehydratedState', {})
            .get('queries', [])
        )

        for q in queries:
            if 'contentAPI.getApi2SnapSnapsByIdV1' in q.get('queryKey', []):
                data = q.get('state', {}).get('data', {}).get('data', {})
                if data:
                    return data

        raise Exception("스냅 상세 원본을 찾을 수 없습니다.")

    def _fetch_goods_batch(self, goods_nos: list) -> list:
        if not goods_nos:
            return []
        formatted_ids = ",".join([f"MUSINSA:{gn}" for gn in goods_nos])
        url = f"https://content.musinsa.com/api2/content/snap/v1/goods?goodsIds={formatted_ids}"
        try:
            res = curl_requests.get(url, impersonate="chrome110", timeout=10).json()
            return res.get('data', {}).get('list', [])
        except Exception:
            return []

    def _upload_images_to_s3(self, snap_id: str, raw_snap_data: dict):
        for media in raw_snap_data.get('medias', []):
            if media.get('type') == 'IMAGE' and media.get('path'):
                s3_key = f"musinsa/snaps/{snap_id}/{_get_filename(media['path'])}"
                media['s3Key'] = self.s3.upload_from_url(media['path'], s3_key)

        for goods in raw_snap_data.get('goods_detail_list', []):
            if goods.get('imageUrl'):
                s3_key = f"musinsa/goods/{goods.get('goodsNo', 'unknown')}/{_get_filename(goods['imageUrl'])}"
                goods['s3ImageKey'] = self.s3.upload_from_url(goods['imageUrl'], s3_key)
