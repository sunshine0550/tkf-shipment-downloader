"""
HTTPS 공용 설정 - access.py / api.py 가 같은 SSL 컨텍스트를 쓴다.

인증서 검증 순서:
  1) truststore : OS 인증서 저장소(윈도우 인증서 저장소 / 맥 키체인)를 사용.
                  회사 보안 프로그램이 HTTPS 를 가로채는(SSL 검사) 환경이라도
                  회사 루트 인증서가 OS 에 설치돼 있으면 브라우저처럼 통과한다.
  2) certifi    : truststore 가 없거나 실패하면 certifi 인증서 묶음 사용.
  3) None       : 둘 다 안 되면 파이썬 기본값.
"""

import ssl
import socket


def _make_ssl_context():
    """(SSL 컨텍스트, 사용한 인증서 출처 이름) 반환."""
    try:
        import truststore
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT), "OS 인증서 저장소(truststore)"
    except Exception:
        pass
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where()), "certifi"
    except Exception:
        return None, "파이썬 기본값"


SSL_CTX, SSL_SOURCE = _make_ssl_context()


def describe_error(e: Exception) -> str:
    """네트워크 예외를 사용자/관리자가 원인을 짐작할 수 있는 한 줄 설명으로 바꾼다."""
    reason = getattr(e, "reason", e)   # URLError 는 실제 원인을 .reason 에 담는다
    raw = f"{type(reason).__name__}: {reason}"
    if isinstance(reason, ssl.SSLCertVerificationError):
        hint = "SSL 인증서 검증 실패 (회사 보안 프로그램의 HTTPS 검사 가능성)"
    elif isinstance(reason, ssl.SSLError):
        hint = "SSL 연결 오류"
    elif isinstance(reason, TimeoutError) or "timed out" in str(reason).lower():
        hint = "응답 시간 초과 (네트워크 느림/차단)"
    elif isinstance(reason, ConnectionRefusedError):
        hint = "연결 거부 (방화벽/프록시 차단 가능성)"
    elif isinstance(reason, ConnectionResetError):
        hint = "연결 끊김 (보안 장비/방화벽 차단 가능성)"
    elif isinstance(reason, socket.gaierror):
        hint = "주소를 찾지 못함 (인터넷/DNS/프록시 문제)"
    else:
        hint = "네트워크 오류"
    return f"{hint}\n[{raw}]"
