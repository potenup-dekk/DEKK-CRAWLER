"""
BatchDelivery retry 로직 단위 테스트

검증 항목:
    create_batch  — 재시도 없음 (fail-fast), batchId None 시 ValueError
    send_raw_data — 5xx/네트워크 오류만 재시도, 4xx는 즉시 실패, 최종 실패 시 ERROR 로그
    complete_batch — 재시도 없음 (fail-fast)

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


def _make_response(status_code: int, json_data: dict = None, text: str = "") -> MagicMock:
    res = MagicMock()
    res.status_code = status_code
    res.json.return_value = json_data or {}
    res.text = text
    if status_code >= 400:
        from requests import HTTPError
        res.raise_for_status.side_effect = HTTPError(response=res)
    else:
        res.raise_for_status.return_value = None
    return res


@pytest.fixture(autouse=True)
def patch_sleep():
    with patch("time.sleep"):
        yield


@pytest.fixture()
def delivery():
    with patch.dict("os.environ", {"BATCH_API_URL": "http://mock-api"}):
        from core.delivery.batch import BatchDelivery
        return BatchDelivery()


# ── create_batch — fail-fast (재시도 없음) ────────────────────────

class TestCreateBatch:
    def test_success_returns_batch_id(self, delivery):
        ok = _make_response(200, {"data": {"batchId": 42}})

        with patch("requests.post", return_value=ok) as mock_post:
            result = delivery.create_batch("MUSINSA")

        assert result == 42
        assert mock_post.call_count == 1

    def test_fails_immediately_on_server_error(self, delivery):
        """5xx여도 재시도 없이 즉시 실패해야 한다 (고아 배치 방지)."""
        from requests import HTTPError
        fail = _make_response(500)

        with patch("requests.post", return_value=fail) as mock_post:
            with pytest.raises(HTTPError):
                delivery.create_batch("MUSINSA")

        assert mock_post.call_count == 1

    def test_raises_value_error_when_batch_id_missing(self, delivery):
        """200이지만 batchId 없으면 ValueError."""
        ok = _make_response(200, {"data": {}}, text='{"data":{}}')

        with patch("requests.post", return_value=ok):
            with pytest.raises(ValueError, match="batchId 없음"):
                delivery.create_batch("MUSINSA")

    def test_fails_immediately_on_4xx(self, delivery):
        from requests import HTTPError
        fail = _make_response(400)

        with patch("requests.post", return_value=fail) as mock_post:
            with pytest.raises(HTTPError):
                delivery.create_batch("MUSINSA")

        assert mock_post.call_count == 1


# ── send_raw_data — 5xx/네트워크만 재시도 ────────────────────────

class TestSendRawData:
    def test_success_on_first_attempt(self, delivery):
        ok = _make_response(200)

        with patch("requests.post", return_value=ok) as mock_post:
            delivery.send_raw_data(1, [{"id": "snap1"}], "2024-01-01T00:00:00")

        assert mock_post.call_count == 1

    def test_retries_on_5xx_then_succeeds(self, delivery):
        fail = _make_response(500)
        ok = _make_response(200)

        with patch("requests.post", side_effect=[fail, ok]) as mock_post:
            delivery.send_raw_data(1, [{"id": "snap1"}], "2024-01-01T00:00:00")

        assert mock_post.call_count == 2

    def test_retries_on_connection_error(self, delivery):
        from requests import ConnectionError as ReqConnError
        ok = _make_response(200)

        with patch("requests.post", side_effect=[ReqConnError(), ok]) as mock_post:
            delivery.send_raw_data(1, [], "2024-01-01T00:00:00")

        assert mock_post.call_count == 2

    def test_no_retry_on_4xx(self, delivery):
        """4xx 클라이언트 오류는 재시도 없이 즉시 실패."""
        from requests import HTTPError
        fail = _make_response(422)

        with patch("requests.post", return_value=fail) as mock_post:
            with pytest.raises(HTTPError):
                delivery.send_raw_data(1, [], "2024-01-01T00:00:00")

        assert mock_post.call_count == 1

    def test_raises_after_max_attempts_on_5xx(self, delivery):
        from requests import HTTPError
        fail = _make_response(500)

        with patch("requests.post", return_value=fail) as mock_post:
            with pytest.raises(HTTPError):
                delivery.send_raw_data(1, [], "2024-01-01T00:00:00")

        assert mock_post.call_count == 3

    def test_logs_error_on_final_failure(self, delivery):
        """3회 모두 실패 시 ERROR 로그가 남아야 한다."""
        fail = _make_response(500)

        with patch("requests.post", return_value=fail):
            with patch("logging.Logger.error") as mock_error:
                with pytest.raises(Exception):
                    delivery.send_raw_data(1, [], "2024-01-01T00:00:00")

        assert mock_error.called

    def test_correct_url_called(self, delivery):
        ok = _make_response(200)

        with patch("requests.post", return_value=ok) as mock_post:
            delivery.send_raw_data(99, [], "2024-01-01T00:00:00")

        assert mock_post.call_args[0][0] == "http://mock-api/batches/99/raw-data"


# ── complete_batch — fail-fast (재시도 없음) ─────────────────────

class TestCompleteBatch:
    def test_success_on_first_attempt(self, delivery):
        ok = _make_response(200)

        with patch("requests.post", return_value=ok) as mock_post:
            delivery.complete_batch(1, 100, "2024-01-01T00:00:00")

        assert mock_post.call_count == 1

    def test_fails_immediately_on_server_error(self, delivery):
        """5xx여도 재시도 없이 즉시 실패해야 한다 (중복 완료 신호 방지)."""
        from requests import HTTPError
        fail = _make_response(500)

        with patch("requests.post", return_value=fail) as mock_post:
            with pytest.raises(HTTPError):
                delivery.complete_batch(1, 100, "2024-01-01T00:00:00")

        assert mock_post.call_count == 1

    def test_error_message_payload(self, delivery):
        ok = _make_response(200)

        with patch("requests.post", return_value=ok) as mock_post:
            delivery.complete_batch(1, 50, "2024-01-01T00:00:00", error_message="timeout")

        payload = mock_post.call_args[1]["json"]
        assert payload["errorMessage"] == "timeout"
        assert payload["totalCount"] == 50
