"""
접근 제어 모듈 - 승인된 PC에서만 프로그램이 실행되도록 제한한다.

동작 방식:
  1) 실행되는 PC의 고유 ID(지문)를 계산한다.
  2) 직접 호스팅하는 tkf-allowlist.json 을 가져온다.
  3) 그 안에 이 PC의 지문이 들어있을 때만 True 를 돌려준다.

allowlist.json 은 어디든 "공개 GET 으로 읽히는 곳"에 올리면 된다:
  - GitHub raw 파일이 가장 쉽다 (예: https://raw.githubusercontent.com/<id>/<repo>/main/allowlist.json)
  - 또는 S3, Google Cloud Storage 공개 객체, 작은 서버 등
  파일을 수정하면 즉시 권한을 주거나 회수할 수 있다.

allowlist.json 형식:
  { "allowed": ["abc123...", "def456..."] }   # 각 항목은 machine_fingerprint() 값

** 클라이언트 측 검사는 작정한 개발자는 우회할 수 있다. 하지만 비개발자 사용자에겐
   충분한 통제 수단이고, 어차피 사이트 로그인(회사 계정)이라는 2차 관문이 또 있다. **
"""

import os
import sys
import ssl
import json
import hashlib
import urllib.request


def _ssl_context():
    """certifi 인증서 묶음으로 SSL 컨텍스트 생성.

    맥의 python.org 파이썬이나 PyInstaller exe 는 시스템 인증서를 못 봐서
    HTTPS 검증이 실패하는 경우가 있다. certifi 를 쓰면 OS 와 무관하게 통과한다.
    certifi 가 없으면 시스템 기본값으로 떨어진다.
    """
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return None


_SSL_CTX = _ssl_context()

# 환경변수 TKF_ALLOWLIST_URL 이 있으면 그것을 우선 사용한다.
# TODO: 본인이 올린 allowlist.json 의 실제 주소로 교체하세요.
ALLOWLIST_URL = os.environ.get(
    "TKF_ALLOWLIST_URL",
    "https://gist.githubusercontent.com/sunshine0550/d2e3c15c79ecc921eb5d1de9109f75f0/raw/tkf-allowlist.json",
)

# 네트워크로 allowlist 를 못 읽었을 때 어떻게 할지.
#   False = 못 읽으면 차단(더 안전)  /  True = 못 읽으면 허용(오프라인 허용)
FAIL_OPEN = False


def get_machine_id() -> str:
    """
    PC마다 고유하고, OS 재설치 전까지 잘 안 바뀌는 ID를 반환.
    윈도우: 레지스트리의 MachineGuid 사용 (가장 안정적)
    그 외(맥 등): 네트워크 어댑터 기반 fallback
    """
    try:
        if sys.platform.startswith("win"):
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
                0,
                winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
            )
            guid, _ = winreg.QueryValueEx(key, "MachineGuid")
            winreg.CloseKey(key)
            return guid.strip()
    except Exception:
        pass

    import uuid
    return str(uuid.getnode())


def machine_fingerprint() -> str:
    """원본 ID를 그대로 노출하지 않도록 해시한 짧은 지문."""
    return hashlib.sha256(get_machine_id().encode("utf-8")).hexdigest()[:16]


def is_authorized() -> bool:
    fp = machine_fingerprint()
    try:
        req = urllib.request.Request(ALLOWLIST_URL, headers={"Cache-Control": "no-cache"})
        with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as r:
            data = json.load(r)
    except Exception:
        return FAIL_OPEN
    return fp in data.get("allowed", [])


if __name__ == "__main__":
    # 사용자가 이 파일만 실행해서 자기 지문을 확인할 수 있게.
    print("이 PC의 머신 ID:", machine_fingerprint())
    print("승인 여부:", "허용됨" if is_authorized() else "거부됨")
