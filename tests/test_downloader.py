"""downloader.py 의 파일명 정제 / 다운로드 저장 로직 테스트.

브라우저(Playwright)는 띄우지 않고, Session 의 네트워크 부분만 가짜로 끼운다.
playwright 패키지가 없으면 이 파일은 통째로 skip 된다.
"""

import pytest

pytest.importorskip("playwright", reason="playwright 미설치 시 다운로더 테스트 skip")

from tkf_downloader import downloader
from tkf_downloader.downloader import Session, _safe


# ---------------------------------------------------------------- _safe()
def test_safe_strips_illegal_chars():
    assert _safe('a/b\\c:d*e?f"g<h>i|j') == "a_b_c_d_e_f_g_h_i_j"


def test_safe_keeps_normal_name():
    assert _safe("invoice_2026.pdf") == "invoice_2026.pdf"


def test_safe_empty_falls_back_to_file():
    # 결과가 '빈 문자열'일 때만 "file" 로 대체된다.
    assert _safe("") == "file"
    assert _safe("   ") == "file"


def test_safe_all_illegal_collapses_to_underscore():
    # 전부 금지문자면 "_" 하나로 축약된다 (빈 값이 아니므로 그대로 유효한 이름).
    assert _safe("///") == "_"


# ---------------------------------------------------- download_all() 모킹 도구
class _FakeResp:
    def __init__(self, body: bytes, ok: bool = True, status: int = 200):
        self._body = body
        self.ok = ok
        self.status = status

    def body(self) -> bytes:
        return self._body


class _FakeRequest:
    """ctx.request.get(url) 흉내. url -> _FakeResp 매핑."""

    def __init__(self, mapping):
        self._mapping = mapping
        self.calls = []

    def get(self, url):
        self.calls.append(url)
        return self._mapping[url]


class _FakeCtx:
    def __init__(self, mapping):
        self.request = _FakeRequest(mapping)


def _make_session(monkeypatch, urls, responses):
    """fetch_document_urls 와 ctx 를 가짜로 끼운 Session 을 만든다."""
    session = Session.__new__(Session)          # __init__/start 우회
    session.log = lambda *a, **k: None
    session.ctx = _FakeCtx(responses)
    monkeypatch.setattr(session, "fetch_document_urls", lambda sid: urls)
    return session


def test_download_all_saves_files(tmp_path, monkeypatch):
    urls = {
        "Invoice": "https://x.test/docs/invoice.pdf",
        "Label": "https://x.test/docs/label.png",
    }
    responses = {
        urls["Invoice"]: _FakeResp(b"PDF-DATA"),
        urls["Label"]: _FakeResp(b"PNG-DATA"),
    }
    session = _make_session(monkeypatch, urls, responses)

    folder, saved = session.download_all("SHIP-1", str(tmp_path))

    assert folder.endswith("SHIP-1")
    assert len(saved) == 2
    names = {p.split("/")[-1] for p in saved}
    assert names == {"invoice.pdf", "label.png"}
    assert (tmp_path / "SHIP-1" / "invoice.pdf").read_bytes() == b"PDF-DATA"


def test_download_all_dedupes_same_basename(tmp_path, monkeypatch):
    # 서로 다른 경로지만 basename 이 같은 두 파일 → 두 번째는 설명 접두사가 붙어야 한다
    urls = {
        "First": "https://x.test/a/doc.pdf",
        "Second": "https://x.test/b/doc.pdf",
    }
    responses = {
        urls["First"]: _FakeResp(b"AAA"),
        urls["Second"]: _FakeResp(b"BBB"),
    }
    session = _make_session(monkeypatch, urls, responses)

    _, saved = session.download_all("SHIP-2", str(tmp_path))

    names = sorted(p.split("/")[-1] for p in saved)
    assert names == ["Second_doc.pdf", "doc.pdf"]
    assert len(set(names)) == 2  # 파일명이 겹치지 않는다


def test_download_all_strips_query_string_from_name(tmp_path, monkeypatch):
    urls = {"Doc": "https://x.test/docs/report.pdf?token=abc123&v=2"}
    responses = {urls["Doc"]: _FakeResp(b"DATA")}
    session = _make_session(monkeypatch, urls, responses)

    _, saved = session.download_all("SHIP-3", str(tmp_path))

    assert saved[0].split("/")[-1] == "report.pdf"


def test_download_all_skips_failed_response(tmp_path, monkeypatch):
    urls = {
        "Good": "https://x.test/ok.pdf",
        "Bad": "https://x.test/bad.pdf",
    }
    responses = {
        urls["Good"]: _FakeResp(b"OK"),
        urls["Bad"]: _FakeResp(b"", ok=False, status=403),
    }
    session = _make_session(monkeypatch, urls, responses)

    _, saved = session.download_all("SHIP-4", str(tmp_path))

    assert len(saved) == 1
    assert saved[0].split("/")[-1] == "ok.pdf"


def test_download_all_no_documents(tmp_path, monkeypatch):
    session = _make_session(monkeypatch, {}, {})

    folder, saved = session.download_all("SHIP-5", str(tmp_path))

    assert saved == []
    assert (tmp_path / "SHIP-5").is_dir()  # 폴더는 만들어진다
