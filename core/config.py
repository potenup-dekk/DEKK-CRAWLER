import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

BASE_DIR = os.path.dirname(CURRENT_DIR)

DATA_DIR = os.path.join(BASE_DIR, 'data')
LOG_DIR = os.path.join(BASE_DIR, 'logs')

STATE_FILE_PATH = os.path.join(DATA_DIR, 'crawler_state.json')

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# ── 파이프라인 설정 ───────────────────────────────────────
MAX_WORKERS = 5
CHUNK_SIZE = 20
INITIAL_MAX_SCROLLS = 40

# ── 공통 네트워크 ─────────────────────────────────────────
CURL_IMPERSONATE = "chrome110"
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# ── Musinsa 크롤러 ────────────────────────────────────────
PLAYWRIGHT_TIMEOUT_MS = 10_000
VIEWPORT_SIZE = {'width': 1920, 'height': 1080}

SNAP_REQUEST_TIMEOUT = 15    # 스냅 상세 페이지 요청 (초)
GOODS_REQUEST_TIMEOUT = 10   # 상품 배치 API 요청 (초)

PROCESS_SLEEP_RANGE = (1.5, 3.5)   # 스냅 처리 전 대기 (방화벽 회피)
SCROLL_SLEEP_RANGE = (1.5, 3.0)    # 페이지 스크롤 후 대기

SNAP_IMAGE_SIZE = (450, 675)    # 스냅 이미지 리사이즈 목표 크기
GOODS_IMAGE_SIZE = (100, 100)   # 상품 이미지 리사이즈 목표 크기

# ── S3 업로더 ─────────────────────────────────────────────
IMAGE_DOWNLOAD_TIMEOUT = 30    # 이미지 다운로드 타임아웃 (초)
IMAGE_DOWNLOAD_MAX_RETRIES = 3
RETRY_SLEEP = 2                # 재시도 대기 시간 (초)
WEBP_QUALITY = 80
