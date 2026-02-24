import time
import json
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from core.s3_uploader import S3Uploader
from .base import BaseCrawler

class MusinsaCrawler(BaseCrawler):
    platform_name = "MUSINSA"
    
    def fetch_new_snaps(self, last_snap_id):
        """Playwright로 스크롤하며 last_snap_id 이전까지의 신규 스냅 ID만 추출 (Delta Crawling)"""
        print(f"🔍 [{self.platform_name}] 신규 스냅 탐색 시작 (마지막 ID: {last_snap_id})")
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

    def process_and_upload(self, snap_id, today_str):
        """HTML에서 원본 데이터를 파싱하고, 상품 히든 API를 찌른 후 S3 및 DTO 생성"""
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

        S3Uploader.upload_raw_json(raw_snap_data, self.platform_name, snap_id, today_str)

        medias = raw_snap_data.get('medias', [])
        original_image_url = medias[0].get('path') if medias else ""
        s3_image_key = S3Uploader.upload_image_from_url(original_image_url, self.platform_name, today_str)

        flat_tags = ",".join([t.get('name', '') for t in raw_snap_data.get('tags', [])])
        
        products_dto = []
        for p in raw_snap_data.get('goods_detail_list', []):
            p_s3_key = S3Uploader.upload_image_from_url(p.get('imageUrl'), self.platform_name, today_str)
            products_dto.append({
                "origin_id": p.get('goodsNo'),
                "name": p.get('goodsName'),
                "price": p.get('normalPrice'),
                "product_image_url": p_s3_key,
                "product_url": p.get('linkUrl'),
                "is_similar": False,
                "option": None
            })

        final_dto = {
            "origin_id": snap_id,
            "card_image_url": s3_image_key,
            "tags": flat_tags,
            "is_active": True,
            "platform": self.platform_name,
            "height": raw_snap_data.get('model', {}).get('height'),
            "weight": raw_snap_data.get('model', {}).get('weight'),
            "products": products_dto
        }
        return final_dto