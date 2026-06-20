"""
순수 HTTP API 클라이언트 (브라우저 없음)

로그인 세션 쿠키(ASP.NET_SessionId 등) 하나만 있으면, 브라우저/Playwright 없이
표준 라이브러리(urllib)로 두 API 를 직접 호출한다:

  1) 검색:  POST GetShipmentHistory   (기간으로 목록)
  2) 상세:  GET  GetShipmentHistoryInfo?deliveryno=..&Shippingno=..&PlantID=..
  3) 문서 URL 들을 쿠키로 직접 GET 해서 저장.

세션이 만료되면 서버가 로그인 페이지(HTML)로 리다이렉트하거나 401/403 을 준다.
그 경우 AuthExpired 를 던져서 호출부가 '재로그인 안내'를 하도록 한다.
"""

import os
import re
import ssl
import json
import time
import urllib.error
import urllib.request
from urllib.parse import urlencode

BASE = "https://lamresearch.myxcarrier.com"
APP_URL = BASE + "/xCarrier/Home/Index"
SEARCH_URL = BASE + "/xCarrier/ECS/GetShipmentHistory?isDemoUrl=true&PageSize=1000000000&PageIndex=1"
DETAIL_URL = BASE + "/xCarrier/ECS/GetShipmentHistoryInfo"

# 검색 payload 고정값 (TKF ↔ Lam1730 계정 기준). 다른 계정/플랜트면 여기만 바꾼다.
SEARCH_PLANT_ID = "Lam1730,"
SEARCH_STATUS_CODE = "SPD"
SEARCH_FEEDERSYSTEM = "All"

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36")


class ApiError(Exception):
    """API 호출 실패 (네트워크/HTTP 오류 등)."""


class AuthExpired(ApiError):
    """세션 쿠키가 만료/무효 → 재로그인이 필요함."""


def _ssl_context():
    """certifi 인증서로 HTTPS 검증 (맥/윈도우/exe 어디서나 통과)."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return None


_SSL_CTX = _ssl_context()


def _safe(name: str) -> str:
    """파일/폴더 이름으로 못 쓰는 문자를 제거."""
    return re.sub(r'[\\/:*?"<>|]+', "_", str(name)).strip() or "file"

def _split_urls(raw: str) -> list:
    """하나로 붙어버린 여러 URL 을 각각으로 분리.

      서버가 DOCUMENT_URL 에 여러 파일을 'https://' 구분 없이 이어 붙여 주는
      경우가 있다. 예:
        'https://.../382126183982.PNGhttps://.../382126183982-1.PNG'
          → ['https://.../382126183982.PNG',
             'https://.../382126183982-1.PNG']
      URL 이 하나뿐이면 그대로 [url] 한 개를 반환한다.
      """
    if not raw:
        return []
    # 'http://' 또는 'https://' 가 시작되는 지점마다 자른다(그 글자는 남김)
    parts = re.split(r'(?=https?://)', raw)
    return [p for p in (s.strip() for s in parts) if p]


class ApiClient:
    """로그인 쿠키 문자열 하나로 동작하는 HTTP 클라이언트."""

    def __init__(self, cookie_header: str, log=print):
        self.cookie = cookie_header
        self.log = log

    def _open(self, url, method="GET", body=None, content_type=None):
        headers = {
            "Cookie": self.cookie,
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": APP_URL,
            "Origin": BASE,
            "User-Agent": _UA,
        }
        if content_type:
            headers["Content-Type"] = content_type
        data = body.encode("utf-8") if isinstance(body, str) else body
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        return urllib.request.urlopen(req, timeout=60, context=_SSL_CTX)

    def _json(self, url, method="GET", body=None, content_type=None):
        try:
            with self._open(url, method, body, content_type) as r:
                ctype = r.headers.get("Content-Type", "")
                raw = r.read()
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise AuthExpired("인증 거부 (로그인 만료)")
            raise ApiError(f"HTTP {e.code}")
        except urllib.error.URLError as e:
            raise ApiError(f"네트워크 오류: {e.reason}")
        if "application/json" not in ctype.lower():
            # 로그인 만료 시 보통 로그인 HTML 로 리다이렉트된다
            raise AuthExpired("응답이 JSON 이 아님 (로그인 만료로 추정)")
        try:
            data = json.loads(raw)
        except Exception:
            raise ApiError("응답 JSON 파싱 실패")
        # 세션 만료 시 이 사이트는 {"isRedirect": true, "logoutUrl": "..."} 를 준다
        if isinstance(data, dict) and (data.get("isRedirect") or data.get("logoutUrl")):
            raise AuthExpired("세션 만료 (로그아웃 리다이렉트 응답)")
        return data

    # ---------------------------------------------------------------- API
    def search_shipments(self, from_date: str, to_date: str) -> list:
        """검색 API → 기간 내 shipment 목록(list[dict]). 날짜는 'MM/DD/YYYY HH:MM:SS'."""
        payload = {
            "FEEDERSYSTEM_NAME": SEARCH_FEEDERSYSTEM,
            "STATUS_CODE": SEARCH_STATUS_CODE,
            "SHIPHISTORY_FROMDATE": from_date,
            "SHIPHISTORY_TODATE": to_date,
            "CARRIER_DESCRIPTION": "",
            "PLANT_ID": SEARCH_PLANT_ID,
        }
        data = self._json(SEARCH_URL, "POST", json.dumps(payload),
                          "application/json; charset=utf-8")
        # (세션 만료 응답은 _json 이 이미 AuthExpired 로 처리함)
        if isinstance(data, str):   # 혹시 문자열로 감싼 JSON 이면 한 번 더 푼다
            try:
                data = json.loads(data)
            except Exception:
                pass
        return data if isinstance(data, list) else []

    def fetch_document_urls(self, row: dict) -> list:
        """상세 API → {설명: DOCUMENT_URL}. row 는 search_shipments() 결과 한 항목."""
        params = urlencode({
            "deliveryno": str(row.get("DELIVERY_NUM", "")),
            "Shippingno": str(row.get("SHIPPING_NUM", "")),
            "PlantID": str(row.get("PLANT_ID", "")),
        })
        data = self._json(DETAIL_URL + "?" + params)
        captured: list[tuple[str, str]] = []
        for d in (data.get("listShipmentDocumentUrls") or []):
            raw_url = d.get("DOCUMENT_URL")
            if not raw_url:
                continue
            desc = d.get("DESCRIPTION")
            for url in _split_urls(raw_url):
                captured.append((desc or url, url))
        return captured

    def download_row(self, row: dict, out_root: str):
        """한 shipment(row)의 모든 문서를 out_root/<DELIVERY_NUM>/ 에 저장.

        반환: (폴더경로, 저장된 파일경로 리스트, 실패목록[(설명, 사유)])
        """
        shipment_id = row.get("DELIVERY_NUM", "unknown")
        urls = self.fetch_document_urls(row)
        folder = os.path.join(out_root, _safe(shipment_id))
        os.makedirs(folder, exist_ok=True)

        saved, failed, seen = [], [], set()
        for desc, url in urls:
            clean = url.split("?")[0]
            fname = _safe(os.path.basename(clean)) or (_safe(desc) + ".bin")
            base, ext = os.path.splitext(fname)
            i = 1
            while fname in seen:
                fname = f"{base}_{i}{ext}"
                i += 1
            seen.add(fname)
            dest = os.path.join(folder, fname)
            reason = self._download_with_retry(url, dest)
            if reason is None:
                saved.append(dest)
                self.log(f"  - 저장: {fname}")
            else:
                self.log(f"  - 실패: {fname} ({reason})")
                failed.append((desc, reason))

        return folder, saved, failed

    # 일시적 오류(네트워크 끊김/타임아웃/5xx)는 최대 2회까지 자동 재시도한다.
    # 401/403/404 처럼 재시도해도 안 풀리는 오류는 즉시 실패 처리한다.
    _MAX_RETRY = 2
    def _download_with_retry(self, url: str, dest: str):
        """url 을 dest 파일로 저장. 성공이면 None, 실패면 사유 문자열을 반환."""
        reason = "알 수 없는 오류"
        for attempt in range(self._MAX_RETRY + 1):   # 처음 1번 + 재시도 2번 = 최대 3번
            try:
                with self._open(url) as r:
                    raw = r.read()
                with open(dest, "wb") as f:
                    f.write(raw)
                return None                            # 성공
            except urllib.error.HTTPError as e:
                if e.code in (401, 403, 404):          # 재시도해도 안 풀림 → 즉시 포기
                    return f"HTTP {e.code}"
                reason = f"HTTP {e.code}"               # 5xx 등은 재시도 대상
            except Exception as e:
                reason = str(e)                         # 네트워크 끊김/타임아웃 등
            if attempt < self._MAX_RETRY:
                self.log(f"  - 재시도 {attempt + 1}/{self._MAX_RETRY} ... ({reason})")
                time.sleep(1.5)
        return reason
