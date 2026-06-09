import ipaddress
import socket
from typing import Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from core.config import BROWSER_USER_AGENT, CURL_IMPERSONATE

STATIC_TIMEOUT = 2

_STATIC_HEADERS = {
    "User-Agent": BROWSER_USER_AGENT,
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]


class InvalidURLError(Exception):
    pass


class SSRFBlockedError(Exception):
    pass


def _is_blocked_ip(ip_str: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip_str)
        return any(addr in net for net in _BLOCKED_NETWORKS)
    except ValueError:
        return True


def validate_and_guard(url: str) -> tuple[str, str]:
    """
    URL 형식 검증 + SSRF 차단.
    통과하면 (resolved_ip, hostname) 반환.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise InvalidURLError(f"유효하지 않은 URL 형식: {url}")

    hostname = parsed.hostname
    if not hostname:
        raise InvalidURLError(f"hostname을 파싱할 수 없음: {url}")

    try:
        results = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise SSRFBlockedError(f"DNS 해석 실패 ({hostname}): {e}")

    if not results:
        raise SSRFBlockedError(f"DNS 결과 없음: {hostname}")

    ip_str = results[0][4][0]

    if _is_blocked_ip(ip_str):
        raise SSRFBlockedError(f"차단된 IP 범위: {ip_str}")

    return ip_str, hostname


def static_fetch(url: str, resolved_ip: str, hostname: str) -> Optional[str]:
    """
    curl_cffi로 정적 HTML fetch. 실패 시 requests로 폴백.
    DNS 리바인딩 방어: 해석된 IP에 직접 연결 + Host 헤더로 원래 hostname 전달.
    """
    parsed = urlparse(url)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    pinned_url = parsed._replace(netloc=f"{resolved_ip}:{port}").geturl()
    headers = {**_STATIC_HEADERS, "Host": hostname}

    try:
        from curl_cffi import requests as cffi_requests
        resp = cffi_requests.get(
            pinned_url,
            headers=headers,
            timeout=STATIC_TIMEOUT,
            impersonate=CURL_IMPERSONATE,
            verify=False,
        )
        resp.raise_for_status()
        return resp.text
    except Exception:
        pass

    try:
        import requests
        resp = requests.get(
            pinned_url,
            headers=headers,
            timeout=STATIC_TIMEOUT,
            verify=False,
        )
        resp.raise_for_status()
        return resp.text
    except Exception:
        return None


def parse_og(html: str, base_url: str) -> dict:
    """BeautifulSoup으로 OG 태그 파싱. 우선순위 체인 적용."""
    soup = BeautifulSoup(html, "html.parser")

    def og(prop: str) -> Optional[str]:
        tag = soup.find("meta", property=prop)
        return tag["content"].strip() if tag and tag.get("content") else None

    def meta_name(name: str) -> Optional[str]:
        tag = soup.find("meta", attrs={"name": name})
        return tag["content"].strip() if tag and tag.get("content") else None

    # productName: og:title → <title>
    product_name = og("og:title")
    if not product_name:
        title_tag = soup.find("title")
        product_name = title_tag.get_text(strip=True) if title_tag else None

    # imageUrl: og:image (상대경로 → 절대경로)
    image_url = og("og:image")
    if image_url and not image_url.startswith("http"):
        image_url = urljoin(base_url, image_url)

    # brandName: og:site_name → <meta name="author">
    brand_name = og("og:site_name") or meta_name("author")

    return {
        "productName": product_name or None,
        "brandName": brand_name or None,
        "imageUrl": image_url or None,
    }


def extract_static(url: str) -> dict:
    """
    SSRF 가드 → 정적 fetch → OG 파싱.
    반환: {"productName", "brandName", "imageUrl", "extracted_via"}
    SSRF/URL 오류 시 {"error", "detail"} 반환.
    """
    try:
        resolved_ip, hostname = validate_and_guard(url)
    except (InvalidURLError, SSRFBlockedError) as e:
        return {"error": "INVALID_URL", "detail": str(e)}

    html = static_fetch(url, resolved_ip, hostname)
    if not html:
        return {
            "productName": None,
            "brandName": None,
            "imageUrl": None,
            "extracted_via": "error",
        }

    og = parse_og(html, url)

    extracted_via = "static" if (og["productName"] or og["imageUrl"]) else "error"

    return {**og, "extracted_via": extracted_via}
