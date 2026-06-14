"""dates.py — 검색 기간 기본값/형식 변환 테스트.

today 를 주입해서 실제 날짜와 무관하게 결정적으로 검증한다.
(playwright 없이도 돈다 — 표준 라이브러리만 사용)
"""

from datetime import date

import pytest

from tkf_downloader import dates

FIXED = date(2026, 6, 13)   # 기준 '오늘'


def test_default_range_is_yesterday_to_today():
    f, t = dates.default_range(FIXED)
    assert f == "06/12/2026 00:00:00"      # 어제 00:00:00
    assert t == "06/13/2026 23:59:59"      # 오늘 23:59:59


def test_default_range_display():
    f, t = dates.default_range_display(FIXED)
    assert f == "06/12/2026"
    assert t == "06/13/2026"


def test_to_api_range_parses_user_input():
    f, t = dates.to_api_range("01/05/2026", "02/10/2026")
    assert f == "01/05/2026 00:00:00"
    assert t == "02/10/2026 23:59:59"


def test_to_api_range_blank_falls_back_to_default():
    # 빈 입력이면 기본(어제/오늘)으로 — 형식만 검증
    f, t = dates.to_api_range("", "")
    assert f.endswith(" 00:00:00")
    assert t.endswith(" 23:59:59")
    assert len(f.split()[0].split("/")) == 3   # MM/DD/YYYY


def test_to_api_range_bad_format_raises():
    with pytest.raises(ValueError):
        dates.to_api_range("2026-06-13", "2026-06-14")   # 잘못된 형식(대시)
