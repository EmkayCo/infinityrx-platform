"""Business day calendar — US federal holidays + configurable bank cutoffs.

Pre-loads 2024-2030 US federal holidays. Validates NACHA effective dates.
Same-day ACH processing windows per NACHA: 1:00 PM, 5:00 PM, 6:00 PM ET.
"""
from __future__ import annotations

from datetime import date, timedelta

# US federal holidays 2024-2030 (static, extend as needed)
_FEDERAL_HOLIDAYS: set[date] = {
    # 2024
    date(2024, 1, 1), date(2024, 1, 15), date(2024, 2, 19), date(2024, 5, 27),
    date(2024, 6, 19), date(2024, 7, 4), date(2024, 9, 2), date(2024, 10, 14),
    date(2024, 11, 11), date(2024, 11, 28), date(2024, 12, 25),
    # 2025
    date(2025, 1, 1), date(2025, 1, 20), date(2025, 2, 17), date(2025, 5, 26),
    date(2025, 6, 19), date(2025, 7, 4), date(2025, 9, 1), date(2025, 10, 13),
    date(2025, 11, 11), date(2025, 11, 27), date(2025, 12, 25),
    # 2026
    date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16), date(2026, 5, 25),
    date(2026, 6, 19), date(2026, 7, 3), date(2026, 9, 7), date(2026, 10, 12),
    date(2026, 11, 11), date(2026, 11, 26), date(2026, 12, 25),
    # 2027
    date(2027, 1, 1), date(2027, 1, 18), date(2027, 2, 15), date(2027, 5, 31),
    date(2027, 6, 18), date(2027, 7, 5), date(2027, 9, 6), date(2027, 10, 11),
    date(2027, 11, 11), date(2027, 11, 25), date(2027, 12, 24),
    # 2028
    date(2028, 1, 17), date(2028, 2, 21), date(2028, 5, 29),
    date(2028, 6, 19), date(2028, 7, 4), date(2028, 9, 4), date(2028, 10, 9),
    date(2028, 11, 10), date(2028, 11, 23), date(2028, 12, 25),
    # 2029
    date(2029, 1, 1), date(2029, 1, 15), date(2029, 2, 19), date(2029, 5, 28),
    date(2029, 6, 19), date(2029, 7, 4), date(2029, 9, 3), date(2029, 10, 8),
    date(2029, 11, 12), date(2029, 11, 22), date(2029, 12, 25),
    # 2030
    date(2030, 1, 1), date(2030, 1, 21), date(2030, 2, 18), date(2030, 5, 27),
    date(2030, 6, 19), date(2030, 7, 4), date(2030, 9, 2), date(2030, 10, 14),
    date(2030, 11, 11), date(2030, 11, 28), date(2030, 12, 25),
}

# Same-day ACH processing window hours (ET) per NACHA
SAME_DAY_ACH_WINDOWS_ET = [13, 17, 18]


def is_business_day(d: date) -> bool:
    """Return True if d is a US federal business day (Mon-Fri, not holiday)."""
    if d.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    return d not in _FEDERAL_HOLIDAYS


def next_business_day(d: date) -> date:
    """Return d itself if it's a business day, else the next business day."""
    candidate = d
    while not is_business_day(candidate):
        candidate = candidate + timedelta(days=1)
    return candidate


def add_business_days(d: date, n: int) -> date:
    """Add n business days to date d."""
    if n < 0:
        raise ValueError("n must be non-negative")
    current = d
    added = 0
    while added < n:
        current = current + timedelta(days=1)
        if is_business_day(current):
            added += 1
    return current


def effective_date_for_batch(submit_date: date, same_day: bool = False) -> date:
    """Return the NACHA effective entry date for a batch submitted on submit_date."""
    if same_day:
        return next_business_day(submit_date)
    return add_business_days(submit_date, 2)
