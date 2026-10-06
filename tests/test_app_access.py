"""app.main() 의 시작 시 접근 판정 테스트 (GUI 는 모두 가짜로 대체)."""

import pytest

from tkf_downloader import app, access


class _FakeRoot:
    def withdraw(self):
        pass

    def mainloop(self):
        pass


class _FakeApp:
    instances = []

    def __init__(self, root):
        self.logs = []
        _FakeApp.instances.append(self)

    def log_threadsafe(self, msg):
        self.logs.append(msg)


@pytest.fixture
def gui(monkeypatch):
    """tk 창/메시지박스/App 을 가짜로 바꾸고, 띄운 에러창 제목을 기록한다."""
    _FakeApp.instances = []
    errors = []
    monkeypatch.setattr(app.tk, "Tk", _FakeRoot)
    monkeypatch.setattr(app, "App", _FakeApp)
    monkeypatch.setattr(app.messagebox, "showerror", lambda title, msg: errors.append(title))
    return errors


def test_allowed_pc_opens_app(gui, monkeypatch):
    monkeypatch.setattr(app, "check_access", lambda: (access.OK, ""))
    app.main()
    assert len(_FakeApp.instances) == 1 and gui == []


def test_unlisted_pc_is_blocked_even_with_fail_open(gui, monkeypatch):
    monkeypatch.setattr(app, "FAIL_OPEN", True)
    monkeypatch.setattr(app, "check_access", lambda: (access.DENIED, ""))
    app.main()
    assert _FakeApp.instances == [] and gui == ["접근 거부"]


def test_unreadable_allowlist_opens_app_with_notice_when_fail_open(gui, monkeypatch):
    monkeypatch.setattr(app, "FAIL_OPEN", True)
    monkeypatch.setattr(app, "check_access",
                        lambda: (access.ERROR, "연결 끊김 (보안 장비/방화벽 차단 가능성)\n[ConnectionResetError]"))
    app.main()
    assert gui == []
    logs = _FakeApp.instances[0].logs
    assert "확인 없이 실행" in logs[0]
    assert "연결 끊김" in logs[1]


def test_unreadable_allowlist_blocks_when_fail_closed(gui, monkeypatch):
    monkeypatch.setattr(app, "FAIL_OPEN", False)
    monkeypatch.setattr(app, "check_access", lambda: (access.ERROR, "x"))
    app.main()
    assert _FakeApp.instances == [] and gui == ["승인 확인 실패"]


def test_fail_open_is_enabled():
    # 회사망 GitHub 차단 대응으로 배포 기본값은 True
    assert access.FAIL_OPEN is True
