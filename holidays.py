"""Offline HK general holidays.

Sources: GovHK gazettes published 2025-05-16 / 2026-05-15.
https://www.info.gov.hk/gia/general/202505/16/P2025051300353p.htm
https://www.info.gov.hk/gia/general/202605/15/P2026051400300p.htm

This module provides offline Hong Kong statutory/general holiday lookups
for 2026 and 2027, as well as workday evaluation helpers used by the
scheduling and recurrence engines.
"""
from datetime import date

# Gazetted 2026 and 2027 Hong Kong general holidays (17 statutory dates per year)
NAMES = ['元旦', '農曆年初一', '農曆年初二', '農曆年初三', '耶穌受難節', '耶穌受難節翌日', '清明節翌日', '復活節星期一翌日', '勞動節', '佛誕翌日', '端午節', '香港特別行政區成立紀念日', '中秋節翌日', '國慶日', '重陽節翌日', '聖誕節', '聖誕節後第一個周日']
DATES_2026 = ['01-01', '02-17', '02-18', '02-19', '04-03', '04-04', '04-06', '04-07', '05-01', '05-25', '06-19', '07-01', '09-26', '10-01', '10-19', '12-25', '12-26']
NAMES_2027 = ['元旦', '農曆年初一', '農曆年初三', '農曆年初四', '耶穌受難節', '耶穌受難節翌日', '復活節星期一', '清明節', '勞動節', '佛誕', '端午節', '香港特別行政區成立紀念日', '中秋節翌日', '國慶日', '重陽節', '聖誕節', '聖誕節後第一個周日']
DATES_2027 = ['01-01', '02-06', '02-08', '02-09', '03-26', '03-27', '03-29', '04-05', '05-01', '05-13', '06-09', '07-01', '09-16', '10-01', '10-08', '12-25', '12-27']

# Combined ISO-date -> Traditional Chinese holiday name lookup table
HOLIDAYS = dict(zip(['2026-' + d for d in DATES_2026], NAMES))
HOLIDAYS.update(zip(['2027-' + d for d in DATES_2027], NAMES_2027))
YEARS = (2026, 2027)


def holiday_name(day):
    """Return the Hong Kong general holiday name for a given date, if any.

    Looks up the date in the preloaded 2026–2027 GovHK holiday mapping. If the
    date is not a gazetted public holiday, falls back to ``'星期日'`` on Sundays.

    Args:
        day (datetime.date): The calendar date to query.

    Returns:
        str: The localized Traditional Chinese name of the holiday or ``'星期日'``
        if ``day`` is a Sunday; otherwise an empty string ``''``.
    """
    # Fall back to '星期日' on Sundays not already covered by a named statutory holiday
    return HOLIDAYS.get(day.isoformat(), '星期日' if day.weekday() == 6 else '')


def is_workday(day, weekdays=(0, 1, 2, 3, 4)):
    """Determine whether a given date counts as a working day.

    A date is considered a workday if its weekday index is included in the
    configured ``weekdays`` sequence and it is not a Hong Kong general holiday.
    Outside the published holiday years (2026–2027), only ``weekdays`` applies.

    Args:
        day (datetime.date): The calendar date to evaluate.
        weekdays (Sequence[int], optional): Weekday indices (0=Monday through
            6=Sunday) designated as regular working days. Defaults to
            ``(0, 1, 2, 3, 4)``.

    Returns:
        bool: ``True`` if ``day`` is a working day; ``False`` otherwise.
    """
    # shortcut: outside published years only the chosen weekdays apply; UI warns about missing holidays.
    return day.weekday() in weekdays and not holiday_name(day)