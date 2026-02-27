# DEKK Crawler

## 데이터 파이프라인 아키텍처

```
크롤링 서버                                  DEKK 서버
    │                                          │
    │  1. 배치 생성                              │
    │  POST /batches ──────────────────────────▶│
    │                                          │  배치 생성 (COLLECTING)
    │  ◀── { batchId: 42 } ───────────────────│
    │                                          │
    │  2. 원본 데이터 전송 (청크 반복)              │
    │  POST /batches/42/raw-data ──────────────▶│
    │  ◀── 200 OK ────────────────────────────│
    │                                          │
    │  POST /batches/42/raw-data ──────────────▶│
    │  ◀── 200 OK ────────────────────────────│
    │  ...                                     │
    │                                          │
    │  3. 수집 완료 통보                           │
    │  POST /batches/42/complete ──────────────▶│
    │                                          │  배치 상태 → COLLECTED
    │  ◀── 200 OK ────────────────────────────│
```

---

## 프로젝트 구조

```
DEKK-CRAWLER/
├── main.py                    # 진입점 - 크롤링 → Batch API 전송 오케스트레이션 (cron)
├── initial_load.py            # 최초 1회 대규모 수집 (~1000건, 병렬 처리)
├── crawlers/
│   ├── base.py                # BaseCrawler 추상 클래스
│   └── musinsa.py             # MusinsaCrawler 구현체
├── core/
│   ├── state_manager.py       # Delta Crawling 상태(last_snap_id) 관리
│   ├── logger.py              # 파일 + 콘솔 로거
│   └── delivery/
│       ├── base.py            # BaseDelivery 추상 클래스
│       ├── batch.py           # BatchDelivery - HTTP POST 3-step 전송
│       └── __init__.py        # DELIVERY_MODE 환경변수로 구현체 선택
├── entrypoint.sh              # Docker 진입점 - 초기 수집 자동 감지 후 cron 시작
├── Dockerfile
├── docker-compose.yml
├── crontab                    # 10분 주기 실행 설정
└── requirements.txt
```

---

## 실행 흐름

```
docker compose up
    └── entrypoint.sh
          ├── [최초] crawler_state.json 없음
          │     └── initial_load.py 실행 (max_scrolls=60, ~1000건, 병렬 수집)
          │           └── 완료 후 last_snap_id 저장
          └── cron 시작
                └── */10 * * * * → main.py (신규 스냅만 delta 수집)
```

---

## 상태 관리 (Delta Crawling)

> ### Delta Crawling (동적 수집 분기 전략)
>
> - **최초 실행 시 (상태 파일 없음)**: `entrypoint.sh`가 `initial_load.py`를 자동 실행. Playwright로 최대 60회 스크롤하여 약 1000건 수집
> - **이후 실행 시 (상태 파일 있음)**: `last_snap_id`를 만날 때까지의 신규 스냅만 가볍게 수집 (10분 주기)

`/app/data/crawler_state.json`에 플랫폼별 마지막 처리 snap ID를 저장합니다.

```json
{
  "MUSINSA": "12345678"
}
```

Docker volume(`./data:/app/data`)으로 마운트되어 컨테이너 재시작 시에도 상태가 유지됩니다.

#### 데이터 유실 방지 (Data Loss Prevention) 및 멱등성 보장

- **상태 갱신 지연**: 크롤링 즉시 상태를 갱신하지 않습니다.
- **안전한 커밋**: Batch API 전송이 최종적으로 성공(`complete` 호출 완료)했을 때만 `last_snap_id`를 갱신합니다.
- **자동 복구**: 네트워크 오류 시 상태가 갱신되지 않으므로, 다음 크론 주기(10분 뒤)에 동일한 데이터를 안전하게 재수집하여 재전송을 시도합니다.

---

## Batch API 페이로드

### 1. 배치 생성 `POST /batches`

```json
{
  "platform": "MUSINSA"
}
```

### 2. 원본 데이터 전송 `POST /batches/{batchId}/raw-data`

청크 단위(20건)로 반복 전송합니다.

```json
{
  "rawData": "[{...스냅 원본 JSON...}, {...}, ...]",
  "crawledAt": "2026-02-26T10:00:00.000000"
}
```

`rawData` 배열 내 각 항목은 무신사 스냅 원본 JSON에 `goods_detail_list` 필드가 추가된 구조입니다.

### 3. 수집 완료 통보 `POST /batches/{batchId}/complete`

```json
{
  "totalCount": 87,
  "completedAt": "2026-02-26T10:05:32.000000",
  "errorMessage": null
}
```

---

## 로깅

`core/logger.py`에서 싱글턴 로거를 생성합니다. 로그는 `/app/data/` 하위에 기록됩니다.

| 파일                    | 내용                                     |
| ----------------------- | ---------------------------------------- |
| `/app/data/crawler.log` | INFO 이상 전체 로그                      |
| `/app/data/error.log`   | ERROR 이상만                             |
| 콘솔 (stdout)           | INFO 이상 전체 (Docker 로그로 확인 가능) |

---

## 환경 변수

`.env` 파일을 프로젝트 루트에 생성하세요.

```dotenv
# Batch API 서버 주소 (/batches 등 경로는 코드 내부에서 붙습니다)
BATCH_API_URL=http://your-spring-boot-server/api

# Delivery 모드 (현재 BATCH만 지원)
DELIVERY_MODE=BATCH
```

---

## 실행 방법

### Docker (권장)

```bash
# 빌드 및 실행
# - 최초: initial_load.py로 ~1000건 수집 후 cron 시작
# - 재시작: 상태 파일이 있으면 바로 cron 시작
docker compose up -d --build

# 로그 확인
docker logs -f integrated-crawler-worker
```

### 로컬 직접 실행

```bash
pip install -r requirements.txt
pip install flask          # mock 서버 사용 시에만 필요
playwright install chromium

# 초기 대용량 수집 (최초 1회)
BATCH_API_URL=http://... DELIVERY_MODE=BATCH python initial_load.py

# 이후 delta 수집 (cron 대신 수동 실행)
BATCH_API_URL=http://... DELIVERY_MODE=BATCH python main.py
```

---

## 의존성

| 패키지           | 용도                                               |
| ---------------- | -------------------------------------------------- |
| `playwright`     | 무신사 스냅 목록 페이지 스크롤 (Headless Chromium) |
| `curl_cffi`      | 스냅 상세 페이지 및 상품 API 호출 (TLS 핑거프린팅 우회) |
| `beautifulsoup4` | `__NEXT_DATA__` 스크립트 태그 파싱                 |
| `requests`       | Batch API HTTP 전송                                |
| `boto3`          | (미사용 예정, 향후 S3 연동 확장 시 활용)           |

---

## 새 크롤러 추가 방법

1. `crawlers/` 하위에 새 파일 생성 (예: `zigzag.py`)
2. `BaseCrawler`를 상속받아 `fetch_new_snaps`와 `process_and_upload`를 구현
3. `main.py`의 `active_crawlers` 리스트에 인스턴스 추가

```python
# main.py
active_crawlers = [
    MusinsaCrawler(),
    ZigzagCrawler(),  # <- 추가
]
```
