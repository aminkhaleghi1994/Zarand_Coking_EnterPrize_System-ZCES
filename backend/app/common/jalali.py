"""Dependency-free Gregorian→Jalali conversion (constitution VIII: no new
runtime dependencies). Implements the standard jalaali algorithm (Jalali
breaks; identical results to the reference `jalaali-js` implementation).

The org's calculation year is the Jalali year (requirements §19). Iran
abolished DST in 2022, so Tehran-local dates are derived with the fixed
UTC+03:30 offset constant below — accurate for all current and foreseeable
Iranian civil time.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

TEHRAN_UTC_OFFSET = timedelta(hours=3, minutes=30)

_BREAKS = (
    -61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210,
    1635, 2060, 2097, 2192, 2262, 2324, 2394, 2456, 3178,
)


def _div(a: int, b: int) -> int:
    """Truncating integer division (the reference algorithm's `~~(a / b)`)."""
    return int(a / b)


def _mod(a: int, b: int) -> int:
    return a - _div(a, b) * b


def _jal_cal(jy: int) -> tuple[int, int, int]:
    """Return (leap, gregorian_year, march_day) for a Jalali year."""
    if jy < _BREAKS[0] or jy >= _BREAKS[-1]:
        raise ValueError(f"Jalali year out of supported range: {jy}")
    leap_j = -14
    jp = _BREAKS[0]
    jump = 0
    for i in range(1, len(_BREAKS)):
        jm = _BREAKS[i]
        jump = jm - jp
        if jy < jm:
            break
        leap_j += _div(jump, 33) * 8 + _div(_mod(jump, 33), 4)
        jp = jm
    n = jy - jp
    leap_j += _div(n, 33) * 8 + _div(_mod(n, 33) + 3, 4)
    if _mod(jump, 33) == 4 and jump - n == 4:
        leap_j += 1
    gy = jy + 621
    leap_g = _div(gy, 4) - _div((_div(gy, 100) + 1) * 3, 4) - 150
    march = 20 + leap_j - leap_g
    if jump - n < 6:
        n = n - jump + _div(jump + 4, 33) * 33
    leap = _mod(_mod(n + 1, 33) - 1, 4)
    if leap == -1:
        leap = 4
    return leap, gy, march


def _g2d(gy: int, gm: int, gd: int) -> int:
    d = (
        _div((gy + _div(gm - 8, 6) + 100100) * 1461, 4)
        + _div(153 * _mod(gm + 9, 12) + 2, 5)
        + gd
        - 1
        - 34840408
    )
    return d - _div(_div(gy + 100100 + _div(gm - 8, 6), 100) * 3, 4) + 752


def _d2g(jdn: int) -> tuple[int, int, int]:
    j = 4 * jdn + 139361631
    j += _div(_div(4 * jdn + 183187720, 146097) * 3, 4) * 4 - 3908
    i = _div(_mod(j, 1461), 4) * 5 + 308
    gd = _div(_mod(i, 153), 5) + 1
    gm = _mod(_div(i, 153), 12) + 1
    gy = _div(j, 1461) - 100100 + _div(8 - gm, 6)
    return gy, gm, gd


def _d2j(jdn: int) -> tuple[int, int, int]:
    gy = _d2g(jdn)[0]
    jy = gy - 621
    leap, _, march = _jal_cal(jy)
    jdn1f = _g2d(gy, 3, march)
    k = jdn - jdn1f
    if k >= 0:
        if k <= 185:
            return jy, 1 + _div(k, 31), _mod(k, 31) + 1
        k -= 186
    else:
        jy -= 1
        k += 179
        if leap == 1:
            k += 1
    return jy, 7 + _div(k, 30), _mod(k, 30) + 1


def gregorian_to_jalali(value: date) -> tuple[int, int, int]:
    """Convert a Gregorian date to (jy, jm, jd)."""
    return _d2j(_g2d(value.year, value.month, value.day))


def jalali_year(value: date) -> int:
    """Jalali year of a Gregorian date."""
    return gregorian_to_jalali(value)[0]


def current_jalali_year(now: datetime | None = None) -> int:
    """Jalali year of the current moment in Tehran civil time.

    `now` may be naive (treated as UTC) or timezone-aware. Tehran's fixed
    +03:30 offset applies (DST abolished in 2022).
    """
    if now is None:
        now = datetime.now(tz=UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    tehran_date = (now + TEHRAN_UTC_OFFSET).date()
    return jalali_year(tehran_date)
