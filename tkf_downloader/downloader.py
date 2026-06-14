"""
다운로드 로직 (Playwright)

핵심 아이디어:
  - 파라미터(shippingno, plantId)를 직접 만들지 않는다.
  - 사람이 하던 검색 동작을 그대로 자동 재생하면, 페이지가 스스로
    GetShipmentHistoryInfo 를 호출한다. 우리는 그 "응답"만 가로채서
    listShipmentDocumentUrls 의 DOCUMENT_URL 들을 받아온다.
  - 받은 URL 들을 "로그인된 세션의 쿠키"로 그대로 GET 해서 파일로 저장한다.

채워야 할 곳: fetch_document_urls() 안의 3개 선택자(SELECTOR_...).
가장 쉬운 방법은 Playwright 의 codegen 으로 직접 녹화하는 것이다 (README 참고):
    playwright codegen https://lamresearch.myxcarrier.com/xCarrier/Home/Index#/ECS/
검색창에 shipment id 입력 → 검색 → 결과 행 클릭, 이 동작을 하면
정확한 선택자 코드가 자동 생성된다. 그 선택자를 아래에 붙여넣으면 된다.
"""

import os
import re
import time

from playwright.sync_api import sync_playwright

BASE = "https://lamresearch.myxcarrier.com"
APP_URL = BASE + "/xCarrier/Home/Index#/ECS/"


def _safe(name: str) -> str:
    """파일/폴더 이름으로 못 쓰는 문자를 제거."""
    return re.sub(r'[\\/:*?"<>|]+', "_", str(name)).strip() or "file"


class Session:
    """브라우저 세션 하나를 소유한다. 반드시 '한 스레드에서만' 사용할 것."""

    def __init__(self, profile_dir: str, log=print, headless: bool = False):
        self.profile_dir = profile_dir
        self.headless = headless
        self.log = log
        self._pw = None
        self.ctx = None
        self.page = None

    def start(self):
        os.makedirs(self.profile_dir, exist_ok=True)
        self._pw = sync_playwright().start()
        # channel="chrome" -> 시스템에 설치된 Google Chrome 사용 (브라우저 번들 불필요)
        # Chrome 이 없으면 channel 줄을 지워서 Playwright 내장 Chromium 을 쓰면 된다.
        self.ctx = self._pw.chromium.launch_persistent_context(
            self.profile_dir,
            channel="chrome",
            headless=self.headless,
            accept_downloads=True,
        )
        self.page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
        self.page.goto(APP_URL, wait_until="domcontentloaded")
        return self

    def close(self):
        try:
            if self.ctx:
                self.ctx.close()
        finally:
            if self._pw:
                self._pw.stop()

    def fetch_document_urls(self, shipment_id: str, timeout_s: int = 60) -> dict:
        """
        검색 UI 를 구동 → GetShipmentHistoryInfo 응답을 가로채 {설명: URL} 반환.
        """
        captured: dict[str, str] = {}

        def on_response(resp):
            if "GetShipmentHistoryInfo" in resp.url:
                try:
                    data = resp.json()
                except Exception:
                    return
                for d in (data.get("listShipmentDocumentUrls") or []):
                    url = d.get("DOCUMENT_URL")
                    if url:
                        key = d.get("DESCRIPTION") or url
                        captured[key] = url

        self.page.on("response", on_response)
        try:
            # ===================================================================
            # TODO: 아래 3줄의 선택자를 실제 사이트에 맞게 교체하세요.
            #       (playwright codegen 으로 녹화하면 정확한 코드가 나옵니다)
            #
            # 1) 검색창에 shipment id 입력
            self.page.fill("SELECTOR_검색입력창", shipment_id)
            # 2) 검색(또는 reference#) 버튼 클릭
            self.page.click("SELECTOR_검색버튼")
            # 3) 결과 목록에서 해당 건의 행을 클릭 → 상세가 열리며 API 호출 발생
            self.page.click(f"text={shipment_id}")
            # ===================================================================

            # 응답이 들어올 때까지 대기 (이벤트는 wait_for_timeout 도중에 처리됨)
            deadline = time.time() + timeout_s
            while time.time() < deadline and not captured:
                self.page.wait_for_timeout(300)
        finally:
            self.page.remove_listener("response", on_response)

        return captured

    def download_all(self, shipment_id: str, out_root: str):
        """
        shipment_id 의 모든 문서를 out_root/<shipment_id>/ 폴더에 저장.
        반환: (폴더경로, 저장된 파일경로 리스트)
        """
        urls = self.fetch_document_urls(shipment_id)
        folder = os.path.join(out_root, _safe(shipment_id))
        os.makedirs(folder, exist_ok=True)

        saved = []
        seen = set()
        for desc, url in urls.items():
            clean = url.split("?")[0]
            fname = _safe(os.path.basename(clean)) or (_safe(desc) + ".bin")
            # 같은 파일명이 겹치면 설명을 접두사로
            if fname in seen:
                fname = _safe(desc) + "_" + fname
            seen.add(fname)

            try:
                # 로그인된 세션의 쿠키로 그대로 GET (인증된 다운로드)
                r = self.ctx.request.get(url)
                if not r.ok:
                    self.log(f"  - 실패({r.status}): {desc}")
                    continue
                path = os.path.join(folder, fname)
                with open(path, "wb") as f:
                    f.write(r.body())
                saved.append(path)
                self.log(f"  - 저장: {fname}")
            except Exception as e:
                self.log(f"  - 오류({desc}): {e}")

        return folder, saved
