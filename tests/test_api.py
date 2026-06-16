"""api.py (순수 HTTP 클라이언트) 테스트.

urllib.request.urlopen 을 가짜로 끼워 네트워크 없이 검증한다.
playwright 와 무관 — api 모듈은 표준 라이브러리만 쓴다.
"""

import io
import json
import urllib.error

import pytest

from tkf_downloader import api
from tkf_downloader.api import ApiClient, ApiError, AuthExpired, _safe


# ---------------------------------------------------------------- _safe()
def test_safe_strips_illegal_chars():
    assert _safe('a/b\\c:d*e?f"g<h>i|j') == "a_b_c_d_e_f_g_h_i_j"


def test_safe_empty_falls_back_to_file():
    assert _safe("") == "file"
    assert _safe("///") == "_"


# ---------------------------------------------------- 가짜 urlopen 도구
class _Resp:
    """urlopen() 반환값(컨텍스트 매니저) 흉내."""

    def __init__(self, body=b"", content_type="application/json; charset=utf-8"):
        self._body = body if isinstance(body, bytes) else body.encode("utf-8")
        self.headers = {"Content-Type": content_type}

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _patch_urlopen(monkeypatch, routes):
    """routes: {url조각: _Resp 또는 raise할 Exception}. req.full_url 로 매칭."""
    def fake(req, timeout=60, context=None):
        url = req.full_url
        for key, resp in routes.items():
            if key in url:
                if isinstance(resp, Exception):
                    raise resp
                return resp
        raise AssertionError(f"예상치 못한 요청: {url}")
    monkeypatch.setattr(api.urllib.request, "urlopen", fake)


def _client():
    return ApiClient("ASP.NET_SessionId=abc", log=lambda *a, **k: None)


# ---------------------------------------------------------------- search
def test_search_returns_list(monkeypatch):
    rows = [{"DELIVERY_NUM": "A1"}, {"DELIVERY_NUM": "A2"}]
    _patch_urlopen(monkeypatch, {"GetShipmentHistory": _Resp(json.dumps(rows))})
    assert _client().search_shipments("06/12/2026 00:00:00", "06/13/2026 23:59:59") == rows


def test_search_non_json_is_auth_expired(monkeypatch):
    # 로그인 만료 시 HTML 로그인 페이지가 온다
    _patch_urlopen(monkeypatch, {"GetShipmentHistory": _Resp("<html>login</html>", "text/html")})
    with pytest.raises(AuthExpired):
        _client().search_shipments("x", "y")


def test_search_redirect_json_is_auth_expired(monkeypatch):
    # 세션 만료 시 {"isRedirect": true, "logoutUrl": "..."} (200 JSON) 를 준다
    redirect = {"isRedirect": True, "logoutUrl": "xCarrierLogin/Logout"}
    _patch_urlopen(monkeypatch, {"GetShipmentHistory": _Resp(json.dumps(redirect))})
    with pytest.raises(AuthExpired):
        _client().search_shipments("x", "y")


def test_search_401_is_auth_expired(monkeypatch):
    err = urllib.error.HTTPError("u", 401, "Unauthorized", {}, io.BytesIO(b""))
    _patch_urlopen(monkeypatch, {"GetShipmentHistory": err})
    with pytest.raises(AuthExpired):
        _client().search_shipments("x", "y")


def test_search_500_is_api_error(monkeypatch):
    err = urllib.error.HTTPError("u", 500, "Server Error", {}, io.BytesIO(b""))
    _patch_urlopen(monkeypatch, {"GetShipmentHistory": err})
    with pytest.raises(ApiError):
        _client().search_shipments("x", "y")


# ---------------------------------------------------------------- detail
def test_fetch_document_urls(monkeypatch):
    detail = {"listShipmentDocumentUrls": [
        {"DOCUMENT_URL": "https://x/LABEL.jpg", "DESCRIPTION": "라벨"},
        {"DOCUMENT_URL": None, "DESCRIPTION": "없음"},
    ]}
    _patch_urlopen(monkeypatch, {"GetShipmentHistoryInfo": _Resp(json.dumps(detail))})
    urls = _client().fetch_document_urls(
        {"DELIVERY_NUM": "A1", "SHIPPING_NUM": 3013834, "PLANT_ID": "Lam1730"})
    # fetch_document_urls 는 (설명, url) 튜플 리스트를 반환한다 (URL 없는 항목은 제외).
    assert urls == [("라벨", "https://x/LABEL.jpg")]


# ---------------------------------------------------------------- download_row
def test_download_row_saves_and_reports(tmp_path, monkeypatch):
    detail = {"listShipmentDocumentUrls": [
        {"DOCUMENT_URL": "https://x/docs/invoice.pdf", "DESCRIPTION": "Invoice"},
        {"DOCUMENT_URL": "https://x/docs/bad.pdf", "DESCRIPTION": "Bad"},
    ]}
    routes = {
        "GetShipmentHistoryInfo": _Resp(json.dumps(detail)),
        "invoice.pdf": _Resp(b"PDFDATA", "application/pdf"),
        "bad.pdf": urllib.error.HTTPError("u", 403, "Forbidden", {}, io.BytesIO(b"")),
    }
    _patch_urlopen(monkeypatch, routes)

    folder, saved, failed = _client().download_row({"DELIVERY_NUM": "SHIP-1"}, str(tmp_path))

    assert [p.split("/")[-1] for p in saved] == ["invoice.pdf"]
    assert (tmp_path / "SHIP-1" / "invoice.pdf").read_bytes() == b"PDFDATA"
    assert failed == [("Bad", "HTTP 403")]


def test_download_row_dedupes_same_basename(tmp_path, monkeypatch):
    detail = {"listShipmentDocumentUrls": [
        {"DOCUMENT_URL": "https://x/a/doc.pdf", "DESCRIPTION": "First"},
        {"DOCUMENT_URL": "https://x/b/doc.pdf", "DESCRIPTION": "Second"},
    ]}
    routes = {
        "GetShipmentHistoryInfo": _Resp(json.dumps(detail)),
        "https://x/a/doc.pdf": _Resp(b"A", "application/pdf"),
        "https://x/b/doc.pdf": _Resp(b"B", "application/pdf"),
    }
    _patch_urlopen(monkeypatch, routes)

    _, saved, _ = _client().download_row({"DELIVERY_NUM": "SHIP-2"}, str(tmp_path))
    # 같은 파일명(doc.pdf)이 겹치면 뒤엣것에 _1 을 붙여 구분한다.
    assert sorted(p.split("/")[-1] for p in saved) == ["doc.pdf", "doc_1.pdf"]
