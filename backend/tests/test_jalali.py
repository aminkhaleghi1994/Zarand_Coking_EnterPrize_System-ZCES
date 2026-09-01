from datetime import UTC, date, datetime, timedelta

import pytest

from app.common.jalali import (
    current_jalali_year,
    gregorian_to_jalali,
    jalali_year,
)

# Reference points: Nowruz (Farvardin 1) is 21 March in common years and
# 20 March after a Jalali leap year; leap years add Esfand 30.


@pytest.mark.parametrize(
    ("gregorian", "expected"),
    [
        (date(2026, 3, 20), (1404, 12, 29)),  # 1404 common: Esfand ends on the 29th
        (date(2026, 3, 21), (1405, 1, 1)),  # Nowruz 1405
        (date(2025, 3, 20), (1403, 12, 30)),  # 1403 leap: Esfand has 30 days
        (date(2025, 3, 21), (1404, 1, 1)),  # Nowruz 1404
        (date(2024, 3, 20), (1403, 1, 1)),  # Nowruz 1403
        (date(2021, 3, 21), (1400, 1, 1)),
        (date(2000, 1, 1), (1378, 10, 11)),
        (date(1979, 2, 11), (1357, 11, 22)),  # Islamic Revolution day
        (date(2026, 9, 1), (1405, 6, 10)),  # today's writing date
        (date(2026, 12, 31), (1405, 10, 10)),  # Gregorian year-end inside Jalali 1405
    ],
)
def test_gregorian_to_jalali_reference_points(
    gregorian: date, expected: tuple[int, int, int]
) -> None:
    assert gregorian_to_jalali(gregorian) == expected


def test_jalali_year_matches_tuple() -> None:
    assert jalali_year(date(2026, 3, 21)) == 1405
    assert jalali_year(date(2026, 3, 20)) == 1404


def _jal_break(jy: int) -> tuple[int, int, int]:
    from app.common.jalali import _jal_cal  # noqa: PLC0415

    return _jal_cal(jy)


def test_every_farvardin_first_maps_to_nowruz() -> None:
    # Farvardin 1 of each Jalali year must land on 20/21 March of gy = jy + 621
    for jy in (1395, 1398, 1403, 1404, 1405, 1408):
        _leap, gy, march = _jal_break(jy)
        assert gregorian_to_jalali(date(gy, 3, march)) == (jy, 1, 1)


def test_leap_years_have_esfand_30() -> None:
    # Known Jalali leap years: 1395, 1399, 1403, 1408 (33-year cycle anchors)
    for jy in (1395, 1399, 1403, 1408):
        leap, _gy, _march = _jal_break(jy)
        assert leap == 0  # leap == 0 means the year IS leap in jalaali
        last_day = gregorian_to_jalali(date(jy + 622, 3, 20))
        assert last_day == (jy, 12, 30)


def test_current_jalali_year_uses_tehran_offset() -> None:
    # 2026-03-20T21:30:00Z is 2026-03-21T01:00 in Tehran → 1405 (not 1404)
    now = datetime(2026, 3, 20, 21, 30, tzinfo=UTC)
    assert current_jalali_year(now) == 1405
    # Naive datetimes are treated as UTC
    assert current_jalali_year(datetime(2026, 3, 20, 21, 30)) == 1405
    # Slightly earlier: still 1404 in both zones
    earlier = now - timedelta(hours=5)
    assert current_jalali_year(earlier) == 1404
