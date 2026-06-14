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

    def fetch_document_urls(self, row: dict) -> dict:
        """상세 API → {설명: DOCUMENT_URL}. row 는 search_shipments() 결과 한 항목."""
        params = urlencode({
            "deliveryno": str(row.get("DELIVERY_NUM", "")),
            "Shippingno": str(row.get("SHIPPING_NUM", "")),
            "PlantID": str(row.get("PLANT_ID", "")),
        })
        data = self._json(DETAIL_URL + "?" + params)
        captured: dict[str, str] = {}
        for d in (data.get("listShipmentDocumentUrls") or []):
            url = d.get("DOCUMENT_URL")
            if url:
                captured[d.get("DESCRIPTION") or url] = url
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
        for desc, url in urls.items():
            clean = url.split("?")[0]
            fname = _safe(os.path.basename(clean)) or (_safe(desc) + ".bin")
            if fname in seen:
                fname = _safe(desc) + "_" + fname
            seen.add(fname)
            try:
                with self._open(url) as r:
                    raw = r.read()
                with open(os.path.join(folder, fname), "wb") as f:
                    f.write(raw)
                saved.append(os.path.join(folder, fname))
                self.log(f"  - 저장: {fname}")
            except urllib.error.HTTPError as e:
                self.log(f"  - 실패(HTTP {e.code}): {desc}")
                failed.append((desc, f"HTTP {e.code}"))
            except Exception as e:
                self.log(f"  - 오류({desc}): {e}")
                failed.append((desc, str(e)))

        return folder, saved, failed
