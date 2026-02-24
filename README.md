# DEKK Crawler

## 데이터 파이프라인 아키텍처

```
[패션 플랫폼]
     │
     │  Playwright(스크롤) + requests(HTML 파싱)
     ▼
[Delta Crawling]  ── last_snap_id 기준 신규 스냅만 추출
     │
     ├──▶ [S3] raw_data/{PLATFORM}/{YYYY/MM/DD}/{snap_id}.json  (원본 JSON 백업)
     │
     ├──▶ [S3] cards/{PLATFORM}/{YYYY/MM/DD}/{filename}         (스냅 이미지)
     │
     └──▶ DTO 생성
               │
               ├── DELIVERY_MODE=SQS   ──▶ [AWS SQS]        ──▶ Consumer (Spring Batch)
               └── DELIVERY_MODE=BATCH ──▶ [Batch API (HTTP)] ──▶ DB 직접 반영
```

---

## S3 데이터 레이아웃

| 경로                                              | 내용                           |
| ------------------------------------------------- | ------------------------------ |
| `raw_data/{PLATFORM}/{YYYY/MM/DD}/{snap_id}.json` | 플랫폼 원본 응답 전체 (백업용) |
| `cards/{PLATFORM}/{YYYY/MM/DD}/{filename}`        | 스냅 대표 이미지               |
| `cards/{PLATFORM}/{YYYY/MM/DD}/{filename}`        | 상품 이미지                    |

---

## DTO 명세

### Card DTO

```json
{
  "origin_id": "12345678",
  "card_image_url": "cards/MUSINSA/2025/01/01/image.jpg",
  "tags": "오버핏,캐주얼,데님",
  "is_active": true,
  "platform": "MUSINSA",
  "height": 180,
  "weight": 65,
  "products": []
}
```

### Product DTO (products 배열 내 항목)

```json
{
  "origin_id": 987654,
  "name": "오버사이즈 데님 재킷",
  "price": 89000,
  "product_image_url": "cards/MUSINSA/2025/01/01/jacket.jpg",
  "product_url": "https://www.musinsa.com/goods/987654",
  "is_similar": false,
  "option": null
}
```

---

## 상태 관리 (Delta Crawling)

`/app/data/crawler_state.json`에 플랫폼별 마지막 처리 snap ID를 저장합니다.

```json
{
  "MUSINSA": "12345678"
}
```

Docker volume(`./data:/app/data`)으로 마운트되어 컨테이너 재시작 시에도 상태가 유지됩니다.
