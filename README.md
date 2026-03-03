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
├── main.py                       # 진입점 - Delta 크롤링 실행 (cron 주기 실행)
├── initial_load.py               # 최초 1회 대규모 수집 (약 1000건, 병렬)
├── requirements.txt              # Python 패키지 의존성
├── .env                          # 환경 변수 설정
├── .gitignore                    # Git 제외 파일 목록
│
├── Dockerfile                    # 크롤러 컨테이너 이미지 정의
├── docker-compose.yml            # Docker 컨테이너 오케스트레이션
├── entrypoint.sh                 # 컨테이너 시작 스크립트
├── crontab                       # 크론 스케줄 설정
│
├── core/                         # 핵심 기능 모듈
│   ├── __init__.py
│   ├── config.py                 # 전역 설정 및 상수 정의
│   ├── logger.py                 # 통합 로깅 시스템
│   ├── pipeline.py               # 크롤링 파이프라인 오케스트레이터
│   ├── s3_uploader.py            # 이미지 및 JSON 백업 S3 업로드
│   ├── backup_handler.py         # 원본 데이터 S3 백업 처리 (중복 제거)
│   ├── state_manager.py          # Delta Crawling 상태 관리 (last_snap_id)
│   └── delivery/                 # 데이터 전송 모듈
│       ├── __init__.py           # Delivery 팩토리
│       ├── base.py               # BaseDelivery 추상 클래스
│       └── batch.py              # BatchDelivery 구현체 (3-step API 전송)
│
├── crawlers/                     # 플랫폼별 크롤러
│   ├── __init__.py
│   ├── base.py                   # BaseCrawler 추상 클래스
└────── musinsa.py                # MusinsaCrawler 구현체

```

**주요 파일 설명**:

| 파일/디렉토리            | 역할                                                        |
| ------------------------ | ----------------------------------------------------------- |
| `main.py`                | 크론 주기 실행 진입점, Delta Crawling 수행                  |
| `initial_load.py`        | 최초 실행 시 대량 데이터 수집 (상태 파일 없을 때 자동 실행) |
| `core/pipeline.py`       | 크롤링 → 백업 → 전송 → 상태 갱신 전체 흐름 조율             |
| `core/s3_uploader.py`    | 이미지 WebP 변환/업로드, 원본 데이터 JSON.GZ 백업           |
| `core/backup_handler.py` | 원본 데이터 추출 및 S3 백업 로직 (중복 제거)                |
| `core/state_manager.py`  | 마지막 처리 ID 관리로 중복 수집 방지                        |
| `core/delivery/`         | Batch API 3-step 전송 (배치 생성 → 데이터 전송 → 완료 통보) |
| `crawlers/musinsa.py`    | 무신사 스냅 크롤링                                          |
| `entrypoint.sh`          | 상태 파일 유무 확인 → 초기 수집 or cron 시작 분기           |

---

## 실행 흐름

```
docker compose up
    └── entrypoint.sh
          ├── [최초] crawler_state.json 없음
          │     └── initial_load.py 실행 (max_scrolls=40, ~1000건, 병렬 수집)
          │           └── 완료 후 last_snap_id 저장
          └── cron 시작
                └── */10 * * * * → main.py (신규 스냅만 delta 수집)
```

---

## 상태 관리 (Delta Crawling)

> ### Delta Crawling (동적 수집 분기 전략)
>
> - **최초 실행 시 (상태 파일 없음)**: `entrypoint.sh`가 `initial_load.py`를 자동 실행. Playwright로 최대 40회 스크롤하여 약 1000건 수집
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

## Batch API 전송 흐름

크롤러는 3단계로 데이터를 전송합니다:

1. **배치 생성** `POST /batches` - 플랫폼 정보와 함께 배치 생성, `batchId` 수신
2. **데이터 전송** `POST /batches/{batchId}/raw-data` - 수집한 스냅 데이터를 청크(20건) 단위로 반복 전송
3. **완료 통보** `POST /batches/{batchId}/complete` - 전송 완료 및 총 개수 전달

---

## 로깅

`core/logger.py`에서 싱글턴 로거를 생성합니다. 로그는 `/app/data/` 하위에 기록됩니다.

| 파일                    | 내용                                     |
| ----------------------- | ---------------------------------------- |
| `/app/logs/crawler.log` | INFO 이상 전체 로그                      |
| `/app/logs/error.log`   | ERROR 이상만                             |
| 콘솔 (stdout)           | INFO 이상 전체 (Docker 로그로 확인 가능) |

---

## 환경 변수

`.env` 파일을 프로젝트 루트에 생성하세요.

```dotenv
# Batch API 서버 주소
BATCH_API_URL=http://your-spring-boot-server/api

# Delivery 모드 (현재 BATCH만 지원)
DELIVERY_MODE=BATCH

# AWS S3 (크롤링한 이미지 저장)
# AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY는 EC2/ECS IAM Role 사용 시 불필요
# 로컬 테스트 시에만 직접 설정
AWS_REGION=ap-northeast-2
S3_BUCKET_NAME=your-bucket-name
```

---

## 실행 방법

```bash
# 빌드 및 실행
# - 최초: initial_load.py로 ~1000건 수집 후 cron 시작
# - 재시작: 상태 파일이 있으면 바로 cron 시작
docker compose up -d --build

# 로그 확인
docker logs -f integrated-crawler-worker
```

---

## 의존성

| 패키지           | 버전    | 용도                                                           |
| ---------------- | ------- | -------------------------------------------------------------- |
| `requests`       | 2.32.5  | Batch API HTTP 요청 (배치 생성, 데이터 전송, 완료 통보)        |
| `boto3`          | 1.42.56 | AWS S3 연동 (이미지 업로드 및 원본 데이터 JSON.GZ 백업)        |
| `beautifulsoup4` | 4.14.3  | HTML 파싱 (`__NEXT_DATA__` 스크립트 태그에서 JSON 추출)        |
| `playwright`     | 1.58.0  | 무신사 스냅 목록 페이지 동적 스크롤 (Headless Chromium)        |
| `python-dotenv`  | 1.0.1   | `.env` 파일에서 환경 변수 로딩                                 |
| `curl_cffi`      | 0.7.4   | TLS 핑거프린팅 우회 (무신사 스냅 상세 페이지 및 상품 API 호출) |
| `Pillow`         | 11.0.0  | 이미지 처리 (WebP 변환 및 리사이징)                            |
