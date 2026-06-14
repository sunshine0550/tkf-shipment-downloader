"""paths.py 의 OS별 다운로드 폴더 해석 테스트.

실제 OS 와 무관하게 sys.platform / home() 을 모킹해서 분기를 검증한다.
(이 테스트는 playwright 가 없어도 돈다 — paths 는 표준 라이브러리만 쓴다.)
"""

import os

from tkf_downloader import paths


def _fake_home(monkeypatch, path):
    monkeypatch.setattr(paths, "home", lambda: path)


def test_mac_uses_home_downloads(monkeypatch):
    monkeypatch.setattr(paths.sys, "platform", "darwin")
    _fake_home(monkeypatch, "/Users/tkf")
    assert paths.downloads_dir() == os.path.join("/Users/tkf", "Downloads")


def test_unknown_os_defaults_to_windows_style(monkeypatch):
    # 판별 불가 OS → 윈도우 기준(홈\Downloads) 기본값
    monkeypatch.setattr(paths.sys, "platform", "sunos5")
    _fake_home(monkeypatch, "/home/tkf")
    assert paths.downloads_dir() == os.path.join("/home/tkf", "Downloads")


def test_windows_falls_back_when_registry_unavailable(monkeypatch):
    # 맥에서 sys.platform 만 'win32' 로 바꾸면 winreg import 가 실패 →
    # _windows_downloads 는 홈\Downloads 로 떨어져야 한다.
    monkeypatch.setattr(paths.sys, "platform", "win32")
    _fake_home(monkeypatch, "C:\\Users\\tkf")
    assert paths.downloads_dir() == os.path.join("C:\\Users\\tkf", "Downloads")


def test_linux_reads_xdg_download_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(paths.sys, "platform", "linux")
    _fake_home(monkeypatch, str(tmp_path))
    cfg_dir = tmp_path / ".config"
    cfg_dir.mkdir()
    (cfg_dir / "user-dirs.dirs").write_text(
        'XDG_DOWNLOAD_DIR="$HOME/내려받기"\n', encoding="utf-8"
    )
    assert paths.downloads_dir() == os.path.join(str(tmp_path), "내려받기")


def test_linux_falls_back_without_xdg_file(monkeypatch, tmp_path):
    monkeypatch.setattr(paths.sys, "platform", "linux")
    _fake_home(monkeypatch, str(tmp_path))  # .config/user-dirs.dirs 없음
    assert paths.downloads_dir() == os.path.join(str(tmp_path), "Downloads")


def test_profile_dir_is_under_home(monkeypatch):
    _fake_home(monkeypatch, "/Users/tkf")
    assert paths.profile_dir() == os.path.join("/Users/tkf", ".tkf_dl_profile")
