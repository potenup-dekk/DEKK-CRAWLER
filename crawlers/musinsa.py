import time
import json
import requests

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from .base import BaseCrawler
from core.logger import logger

class MusinsaCrawler(BaseCrawler):
    platform_name = "MUSINSA"
    
    def fetch_new_snaps(self, last_snap_id):
        """Playwright로 스크롤하며 last_snap_id 이전까지의 신규 스냅 ID만 추출 (Delta Crawling)"""
        logger.info(f"🔍 [{self.platform_name}] 신규 스냅 탐색 시작 (마지막 ID: {last_snap_id})")
        
        new_ids = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent="Mozilla/5.0")
            page.goto("https://www.musinsa.com/snap?sort=NEWEST")
            page.wait_for_load_state("networkidle")

            found_last = False
            for _ in range(5):
                links = page.locator("a[href*='/snap/']").all()
                for link in links:
                    href = link.get_attribute("href")
                    if not href: continue
                    
                    snap_id = href.split('/snap/')[-1].split('?')[0]
                    if not snap_id.isdigit(): continue

                    if snap_id == last_snap_id:
                        found_last = True
                        break
                        
                    if snap_id not in new_ids:
                        new_ids.append(snap_id)

                if found_last: break
                page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1.5)
                
            browser.close()
        
        return new_ids[::-1]

    def _fetch_goods_batch(self, goods_nos):
        if not goods_nos: return []
        formatted_ids = ",".join([f"MUSINSA:{gn}" for gn in goods_nos])
        url = f"https://content.musinsa.com/api2/content/snap/v1/goods?goodsIds={formatted_ids}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        try:
            res = requests.get(url, headers=headers).json()
            return res.get('data', {}).get('list', [])
        except Exception:
            return []

    def process_and_upload(self, snap_id):
        url = f"https://www.musinsa.com/snap/{snap_id}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        script_tag = soup.find('script', id='__NEXT_DATA__')
        if not script_tag: raise Exception("NEXT_DATA 파싱 실패")

        json_data = json.loads(script_tag.string)
        queries = json_data.get('props', {}).get('pageProps', {}).get('dehydratedState', {}).get('queries', [])
        
        raw_snap_data = {}
        for q in queries:
            if 'contentAPI.getApi2SnapSnapsByIdV1' in q.get('queryKey', []):
                raw_snap_data = q.get('state', {}).get('data', {}).get('data', {})
                break

        if not raw_snap_data: raise Exception("스냅 상세 원본을 찾을 수 없습니다.")

        goods_list_raw = raw_snap_data.get('goods', [])
        goods_nos = [str(g.get('goodsNo')) for g in goods_list_raw if g.get('goodsNo')]
        raw_snap_data['goods_detail_list'] = self._fetch_goods_batch(goods_nos)

        payload = {
            "platform": self.platform_name,
            "origin_id": str(snap_id),
            "raw_data": json.dumps(raw_snap_data, ensure_ascii=False) 
        }

        return payload
