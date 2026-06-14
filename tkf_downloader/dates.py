"""검색 기간(날짜) 처리.

사이트 검색 API(GetShipmentHistory)는 날짜를 'MM/DD/YYYY HH:MM:SS' 형식으로 받는다.
  - 시작일은 00:00:00, 종료일은 23:59:59 로 맞춘다.
기본 검색 기간은 '어제 ~ 오늘' 이다.
"""

from datetime import date, datetime, timedelta


def _fmt_from(d: date) -> str:
    return d.strftime("%m/%d/%Y") + " 00:00:00"


def _fmt_to(d: date) -> str:
    return d.strftime("%m/%d/%Y") + " 23:59:59"


def default_range(today=None):
    """기본 검색 기간(API 형식): 어제 00:00:00 ~ 오늘 23:59:59."""
    today = today or date.today()
    return _fmt_from(today - timedelta(days=1)), _fmt_to(today)


def default_range_display(today=None):
    """GUI 입력칸 기본값: ('MM/DD/YYYY', 'MM/DD/YYYY') = (어제, 오늘)."""
    today = today or date.today()
    yesterday = today - timedelta(days=1)
    return yesterday.strftime("%m/%d/%Y"), today.strftime("%m/%d/%Y")


def to_api_range(from_text: str, to_text: str):
    """GUI 에 입력된 'MM/DD/YYYY' 두 개 → API 형식 (from 00:00:00, to 23:59:59).

    빈 칸이면 기본(어제/오늘)으로 대체한다. 형식이 틀리면 ValueError 를 던진다.
    """
    df, dt = default_range_display()
    from_text = (from_text or df).strip()
    to_text = (to_text or dt).strip()
    f = datetime.strptime(from_text, "%m/%d/%Y").date()
    t = datetime.strptime(to_text, "%m/%d/%Y").date()
    return _fmt_from(f), _fmt_to(t)
