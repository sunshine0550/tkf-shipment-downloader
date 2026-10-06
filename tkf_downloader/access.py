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
import json
import hashlib
import urllib.request

from .net import SSL_CTX, SSL_SOURCE, describe_error

# 환경변수 TKF_ALLOWLIST_URL 이 있으면 그것을 우선 사용한다.
# TODO: 본인이 올린 allowlist.json 의 실제 주소로 교체하세요.
ALLOWLIST_URL = os.environ.get(
    "TKF_ALLOWLIST_URL",
    "https://gist.githubusercontent.com/sunshine0550/d2e3c15c79ecc921eb5d1de9109f75f0/raw/tkf-allowlist.json",
)

# 네트워크로 allowlist 를 못 읽었을 때 어떻게 할지.
#   False = 못 읽으면 차단(더 안전)  /  True = 못 읽으면 허용(오프라인 허용)
# True 인 이유: 일부 회사망은 브라우저 외 프로그램의 GitHub(Gist) 접속을 차단한다
#   (연결 끊김, WinError 10054). 그런 PC도 쓸 수 있게 하되, 명단을 읽었는데
#   ID 가 없는 경우는 여전히 차단한다.
FAIL_OPEN = True


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


# check_access() 결과 상태
OK = "ok"            # 명단에 있음 → 사용 가능
DENIED = "denied"    # 명단은 읽었는데 이 PC가 없음
ERROR = "error"      # 명단 자체를 못 읽음 (네트워크/SSL/형식 문제)


def check_access():
    """(상태, 상세) 반환. 상태는 OK / DENIED / ERROR.

    ERROR 일 때 상세에는 실제 원인(SSL 검증 실패, 시간 초과 등)이 들어간다.
    """
    fp = machine_fingerprint()
    try:
        req = urllib.request.Request(ALLOWLIST_URL, headers={"Cache-Control": "no-cache"})
        with urllib.request.urlopen(req, timeout=10, context=SSL_CTX) as r:
            raw = r.read()
    except Exception as e:
        return ERROR, f"{describe_error(e)}\n[인증서: {SSL_SOURCE}]"
    try:
        data = json.loads(raw)
        allowed = data.get("allowed", [])
    except Exception:
        # 프록시 로그인/차단 페이지(HTML)가 대신 돌아온 경우 등
        head = raw[:80].decode("utf-8", "replace").replace("\n", " ")
        return ERROR, f"승인 명단 형식이 아님 (프록시/차단 페이지 가능성)\n[응답 앞부분: {head}]"
    return (OK, "") if fp in allowed else (DENIED, "")


def is_authorized() -> bool:
    status, _ = check_access()
    if status == ERROR:
        return FAIL_OPEN
    return status == OK


if __name__ == "__main__":
    # 사용자가 이 파일만 실행해서 자기 지문을 확인할 수 있게.
    print("이 PC의 머신 ID:", machine_fingerprint())
    status, detail = check_access()
    print("승인 여부:", {OK: "허용됨", DENIED: "거부됨 (명단에 없음)", ERROR: "확인 불가"}[status])
    if detail:
        print(detail)
