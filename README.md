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
               └── DELIVERY_MODE=BATCH ──▶ [Batch API (HTTP)] ──▶ Queue 테이블 적재
```

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
// Example
{
  "origin_id": "12345678",
  "card_image_url": "cards/MUSINSA/2025/01/01/image.jpg",
  "tags": "오버핏,캐주얼,데님",
  "is_active": true,
  "platform": "MUSINSA",
  "height": 180,
  "weight": 65,
  "created_at": "2026-02-25T17:28:25+09:00",
  "products": []
}
```

### Product DTO (products 배열 내 항목)

```json
// Example
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

> ### Delta Crawling (동적 수집 분기 전략)
>
> - **최초 실행 시 (상태 파일 없음)**: 최근 트렌드 기준 약 1,000개 대량 수집 (초기화)
> - **이후 실행 시 (상태 파일 있음)**: last_snap_id를 만날 때까지의 신규 스냅만 가볍게 수집 (10분 주기)

`/app/data/crawler_state.json`에 플랫폼별 마지막 처리 snap ID를 저장합니다.

```json
{
  "MUSINSA": "12345678"
}
```

Docker volume(`./data:/app/data`)으로 마운트되어 컨테이너 재시작 시에도 상태가 유지됩니다.

#### 데이터 유실 방지 (Data Loss Prevention) 및 멱등성 보장

- **상태 갱신 지연**: 크롤링 즉시 상태를 갱신하지 않습니다.

- **안전한 커밋**: Spring Boot의 Batch API 전송이 최종적으로 성공(HTTP 200 OK)했을 때만 last_snap_id를 갱신합니다.

- **자동 복구**: 네트워크 오류 시 상태가 갱신되지 않으므로, 다음 크론 주기(10분 뒤)에 동일한 데이터를 안전하게 재수집하여 재전송을 시도합니다.
