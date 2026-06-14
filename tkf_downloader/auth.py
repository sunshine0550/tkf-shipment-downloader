"""
로그인 세션 쿠키 관리

- 캐시: 캡처한 쿠키 문자열을 파일(`~/.tkf_session`)에 저장/로드.
- 캡처: 쿠키가 없거나 만료됐을 때만 브라우저(Playwright)를 띄워 사용자가 로그인하게 하고,
        로그인이 감지되면 세션 쿠키를 뽑아 저장한 뒤 브라우저를 닫는다.

** 로그인 자체(MS 로그인 + MFA)는 자동화하지 않는다(불가/위험). 사람이 통과하면
   그 결과로 생긴 쿠키만 재사용한다. 평소 작업은 이 쿠키로 순수 HTTP(브라우저 없음). **
"""

import os

from .paths import cookie_file, profile_dir


def load_cookie_header():
    """저장된 쿠키 문자열을 돌려준다. 없으면 None."""
    try:
        with open(cookie_file(), encoding="utf-8") as f:
            return f.read().strip() or None
    except Exception:
        return None


def save_cookie_header(header: str):
    with open(cookie_file(), "w", encoding="utf-8") as f:
        f.write(header)


def clear_cookie():
    try:
        os.remove(cookie_file())
    except Exception:
        pass


def _cookie_header_from(cookies) -> str:
    """Playwright context.cookies() → 'name=value; ...' 헤더 문자열."""
    wanted = [c for c in cookies if "myxcarrier.com" in (c.get("domain") or "")]
    return "; ".join(f"{c['name']}={c['value']}" for c in wanted)


def capture_cookie_via_browser(log=print, timeout_s: int = 300) -> str:
    """브라우저를 띄워 사용자가 로그인하게 하고, 로그인 감지 시 세션 쿠키를 저장/반환.

    로그인 여부는 'ASP.NET_SessionId 쿠키 존재 + 검색 API 가 JSON 응답'으로 판정한다.
    """
    from playwright.sync_api import sync_playwright

    from .api import APP_URL

    pdir = profile_dir()
    os.makedirs(pdir, exist_ok=True)
    pw = sync_playwright().start()
    ctx = pw.chromium.launch_persistent_context(
        pdir, channel="chrome", headless=False, accept_downloads=True
    )
    try:
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(APP_URL, wait_until="domcontentloaded")
        log("브라우저에서 로그인하세요. 로그인되면 자동으로 감지하고 창을 닫습니다...")

        # 로그인 완료 판정: SPA 가 sessionStorage 에 USERNAME 을 채우면 로그인된 것.
        # (이 사이트는 세션 만료 시에도 로그인 페이지가 아니라 빈 JSON 을 주므로,
        #  검색 결과로는 로그인 여부를 알 수 없다 → sessionStorage 로 확실히 판정한다.)
        header = None
        for _ in range(max(1, timeout_s // 2)):
            try:
                user = page.evaluate("() => window.sessionStorage.getItem('USERNAME')")
            except Exception:
                user = None   # 로그인 진행 중(MS 페이지 등 다른 origin) → 아직
            if user:
                cookies = ctx.cookies()
                if any(c.get("name") == "ASP.NET_SessionId" for c in cookies):
                    header = _cookie_header_from(cookies)
                    log(f"로그인 확인: {user}")
                    break
            page.wait_for_timeout(2000)

        if not header:
            raise RuntimeError("로그인 감지 실패 (시간 초과). 다시 시도하세요.")

        save_cookie_header(header)
        log("로그인 완료 — 세션 쿠키를 저장했습니다.")
        return header
    finally:
        try:
            ctx.close()
        finally:
            pw.stop()
