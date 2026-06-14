"""access.py 접근 제어 로직 테스트 (네트워크는 모두 모킹)."""

import hashlib
import io
import json

import pytest

from tkf_downloader import access


def test_machine_fingerprint_is_16_hex():
    fp = access.machine_fingerprint()
    assert len(fp) == 16
    assert all(c in "0123456789abcdef" for c in fp)


def test_machine_fingerprint_is_deterministic():
    assert access.machine_fingerprint() == access.machine_fingerprint()


def test_machine_fingerprint_matches_sha256_of_machine_id(monkeypatch):
    monkeypatch.setattr(access, "get_machine_id", lambda: "FIXED-ID")
    expected = hashlib.sha256(b"FIXED-ID").hexdigest()[:16]
    assert access.machine_fingerprint() == expected


class _FakeResponse:
    """urlopen() 이 돌려주는 context manager 흉내."""

    def __init__(self, payload: dict):
        self._buf = io.BytesIO(json.dumps(payload).encode("utf-8"))

    def __enter__(self):
        return self._buf

    def __exit__(self, *exc):
        return False


def _patch_allowlist(monkeypatch, payload):
    monkeypatch.setattr(
        access.urllib.request,
        "urlopen",
        lambda req, timeout=10, context=None: _FakeResponse(payload),
    )


def test_authorized_when_fingerprint_in_allowlist(monkeypatch):
    monkeypatch.setattr(access, "machine_fingerprint", lambda: "abc123")
    _patch_allowlist(monkeypatch, {"allowed": ["abc123", "other"]})
    assert access.is_authorized() is True


def test_denied_when_fingerprint_absent(monkeypatch):
    monkeypatch.setattr(access, "machine_fingerprint", lambda: "abc123")
    _patch_allowlist(monkeypatch, {"allowed": ["other"]})
    assert access.is_authorized() is False


def test_denied_when_allowed_key_missing(monkeypatch):
    monkeypatch.setattr(access, "machine_fingerprint", lambda: "abc123")
    _patch_allowlist(monkeypatch, {})
    assert access.is_authorized() is False


def test_network_error_respects_fail_open_false(monkeypatch):
    def boom(req, timeout=10, context=None):
        raise OSError("network down")

    monkeypatch.setattr(access.urllib.request, "urlopen", boom)
    monkeypatch.setattr(access, "FAIL_OPEN", False)
    assert access.is_authorized() is False


def test_network_error_respects_fail_open_true(monkeypatch):
    def boom(req, timeout=10, context=None):
        raise OSError("network down")

    monkeypatch.setattr(access.urllib.request, "urlopen", boom)
    monkeypatch.setattr(access, "FAIL_OPEN", True)
    assert access.is_authorized() is True
