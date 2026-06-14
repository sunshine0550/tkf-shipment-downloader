"""OS 별 경로 해석 (맥 / 윈도우 / 리눅스 공용).

다운로드한 파일은 각 OS 의 '다운로드' 폴더 아래에 저장한다.
  - 윈도우: 사용자가 '다운로드' 폴더 위치를 옮겼을 수 있으므로 레지스트리에서
            실제 경로를 읽는다. 실패하면 ~\\Downloads 로 떨어진다.
  - 맥:     항상 ~/Downloads
  - 리눅스: XDG user-dirs(있으면) → 없으면 ~/Downloads
  - 그 외 / 판별 불가: ** 윈도우 기준(~\\Downloads) 을 기본값으로 한다. **
"""

import os
import sys

# 윈도우 '알려진 폴더(Known Folder)' 중 Downloads 의 GUID
_WIN_DOWNLOADS_GUID = "{374DE290-123F-4565-9164-39C4925E467B}"


def home() -> str:
    return os.path.expanduser("~")


def _windows_downloads() -> str:
    """레지스트리에서 실제 Downloads 경로를 읽고, 안 되면 ~\\Downloads."""
    fallback = os.path.join(home(), "Downloads")
    try:
        import winreg
        sub = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub) as key:
            value, _ = winreg.QueryValueEx(key, _WIN_DOWNLOADS_GUID)
        value = os.path.expandvars(value)
        return value or fallback
    except Exception:
        # winreg 가 없는(=윈도우가 아닌) 환경이거나 키가 없으면 기본값
        return fallback


def _xdg_downloads() -> str:
    """리눅스: ~/.config/user-dirs.dirs 의 XDG_DOWNLOAD_DIR → 없으면 ~/Downloads."""
    fallback = os.path.join(home(), "Downloads")
    cfg = os.path.join(home(), ".config", "user-dirs.dirs")
    try:
        with open(cfg, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("XDG_DOWNLOAD_DIR"):
                    raw = line.split("=", 1)[1].strip().strip('"')
                    raw = raw.replace("$HOME", home())
                    return os.path.expandvars(raw) or fallback
    except Exception:
        pass
    return fallback


def downloads_dir() -> str:
    """현재 OS 에 맞는 '다운로드' 폴더 경로를 돌려준다."""
    if sys.platform.startswith("win"):
        return _windows_downloads()
    if sys.platform == "darwin":
        return os.path.join(home(), "Downloads")
    if sys.platform.startswith("linux"):
        return _xdg_downloads()
    # 알 수 없는 OS → 윈도우 기준 기본값
    return os.path.join(home(), "Downloads")


def profile_dir() -> str:
    """로그인 세션(브라우저 프로필) 저장 위치. 모든 OS 에서 홈 아래 숨김 폴더."""
    return os.path.join(home(), ".tkf_dl_profile")
