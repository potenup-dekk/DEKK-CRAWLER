"""
BatchDelivery retry 로직 단위 테스트

검증 항목:
    1. 첫 시도에 성공하면 retry 없이 반환
    2. N회 실패 후 성공하면 정상 반환
    3. 3회 모두 실패하면 예외 전파
    4. 각 메서드(create_batch, send_raw_data, complete_batch) 독립 검증

실행:
    python -m pytest test/test_batch_delivery_retry.py -v
"""

import logging
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

# core.logger가 import 시점에 /app/logs/crawler.log를 열려 해서
# sys.modules에 mock을 먼저 꽂아 Docker 경로 의존성을 차단한다.
_mock_logger_module = ModuleType("core.logger")
_mock_logger_module.logger = logging.getLogger("test")
sys.modules.setdefault("core.logger", _mock_logger_module)


def _make_response(status_code: int, json_data: dict = None) -> MagicMock:
    res = MagicMock()
    res.status_code = status_code
    res.json.return_value = json_data or {}
    if status_code >= 400:
        from requests import HTTPError
        res.raise_for_status.side_effect = HTTPError(response=res)
    else:
        res.raise_for_status.return_value = None
    return res


@pytest.fixture(autouse=True)
def patch_sleep():
    """tenacity의 대기 시간을 0으로 만들어 테스트 속도 보장"""
    with patch("time.sleep"):
        yield


@pytest.fixture()
def delivery():
    with patch.dict("os.environ", {"BATCH_API_URL": "http://mock-api"}):
        from core.delivery.batch import BatchDelivery
        return BatchDelivery()


# ── create_batch ──────────────────────────────────────────────────

class TestCreateBatch:
    def test_success_on_first_attempt(self, delivery):
        ok_res = _make_response(200, {"data": {"batchId": 42}})

        with patch("requests.post", return_value=ok_res) as mock_post:
            result = delivery.create_batch("MUSINSA")

        assert result == 42
        assert mock_post.call_count == 1

    def test_retry_twice_then_succeed(self, delivery):
        fail = _make_response(500)
        ok = _make_response(200, {"data": {"batchId": 7}})

        with patch("requests.post", side_effect=[fail, fail, ok]) as mock_post:
            result = delivery.create_batch("MUSINSA")

        assert result == 7
        assert mock_post.call_count == 3

    def test_raises_after_max_attempts(self, delivery):
        from requests import HTTPError
        fail = _make_response(500)

        with patch("requests.post", return_value=fail):
            with pytest.raises(HTTPError):
                delivery.create_batch("MUSINSA")

    def test_call_count_equals_max_attempts_on_failure(self, delivery):
        fail = _make_response(500)

        with patch("requests.post", return_value=fail) as mock_post:
            with pytest.raises(Exception):
                delivery.create_batch("MUSINSA")

        assert mock_post.call_count == 3


# ── send_raw_data ─────────────────────────────────────────────────

class TestSendRawData:
    def test_success_on_first_attempt(self, delivery):
        ok = _make_response(200)

        with patch("requests.post", return_value=ok) as mock_post:
            delivery.send_raw_data(1, [{"id": "snap1"}], "2024-01-01T00:00:00")

        assert mock_post.call_count == 1

    def test_retry_once_then_succeed(self, delivery):
        fail = _make_response(503)
        ok = _make_response(200)

        with patch("requests.post", side_effect=[fail, ok]) as mock_post:
            delivery.send_raw_data(1, [{"id": "snap1"}], "2024-01-01T00:00:00")

        assert mock_post.call_count == 2

    def test_raises_after_max_attempts(self, delivery):
        from requests import HTTPError
        fail = _make_response(503)

        with patch("requests.post", return_value=fail):
            with pytest.raises(HTTPError):
                delivery.send_raw_data(1, [], "2024-01-01T00:00:00")

    def test_correct_url_called(self, delivery):
        ok = _make_response(200)

        with patch("requests.post", return_value=ok) as mock_post:
            delivery.send_raw_data(99, [], "2024-01-01T00:00:00")

        called_url = mock_post.call_args[0][0]
        assert called_url == "http://mock-api/batches/99/raw-data"


# ── complete_batch ────────────────────────────────────────────────

class TestCompleteBatch:
    def test_success_on_first_attempt(self, delivery):
        ok = _make_response(200)

        with patch("requests.post", return_value=ok) as mock_post:
            delivery.complete_batch(1, 100, "2024-01-01T00:00:00")

        assert mock_post.call_count == 1

    def test_retry_and_succeed(self, delivery):
        fail = _make_response(500)
        ok = _make_response(200)

        with patch("requests.post", side_effect=[fail, ok]) as mock_post:
            delivery.complete_batch(1, 100, "2024-01-01T00:00:00")

        assert mock_post.call_count == 2

    def test_raises_after_max_attempts(self, delivery):
        from requests import HTTPError
        fail = _make_response(500)

        with patch("requests.post", return_value=fail):
            with pytest.raises(HTTPError):
                delivery.complete_batch(1, 100, "2024-01-01T00:00:00")

    def test_error_message_payload(self, delivery):
        ok = _make_response(200)

        with patch("requests.post", return_value=ok) as mock_post:
            delivery.complete_batch(1, 50, "2024-01-01T00:00:00", error_message="timeout")

        payload = mock_post.call_args[1]["json"]
        assert payload["errorMessage"] == "timeout"
        assert payload["totalCount"] == 50
