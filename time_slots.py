"""Shared half-hour clock parsing for event and timetable modules.

This module defines standardized error message constants and a reusable clock-string
parser that converts ``HH:MM`` timestamps (aligned to 30-minute increments within
``00:00``–``24:00``) into integer minutes elapsed since midnight.
"""

# Standardized localization messages for event and timetable clock validation
EVENT_MISSING_TIME = '請填寫半小時單位的時間，例如 09:00 或 09:30。'
EVENT_INVALID_TIME = '時間須為 00:00–24:00，並以半小時為單位。'
TIMETABLE_MISSING_TIME = '請填寫時間，例如 18:00 或 18:30。'
TIMETABLE_INVALID_TIME = '時間以半小時為單位，範圍為 00:00–24:00。'


def parse_clock(value, missing_message, invalid_message):
    """Parse an ``HH:MM`` clock string into minutes since midnight.

    Validates that ``value`` splits cleanly into integer hours and minutes, falls
    within ``00:00`` through ``24:00`` inclusive, and aligns to a half-hour
    boundary (``00`` or ``30`` minutes, with ``24:00`` as the sole valid hour-24 value).

    Args:
        value (str): Time string formatted as ``HH:MM`` (e.g., ``"09:00"`` or ``"18:30"``).
        missing_message (str): Error message raised when ``value`` is missing, non-string,
            or lacks a valid ``HH:MM`` colon-separated integer structure.
        invalid_message (str): Error message raised when the parsed hour or minute
            violates the ``00:00``–``24:00`` range or 30-minute step constraint.

    Returns:
        int: Total minutes elapsed since ``00:00`` (ranging from ``0`` to ``1440``).

    Raises:
        ValueError: With ``missing_message`` if ``value`` cannot be split into two
            integers, or with ``invalid_message`` if the time is out of range or
            not aligned to a half-hour boundary.
    """
    try:
        hour, minute = map(int, value.split(':'))
    except (ValueError, AttributeError):
        raise ValueError(missing_message) from None
    # Allow 00:00..24:00 on 30-minute steps, rejecting 24:30
    if not 0 <= hour <= 24 or minute not in (0, 30) or (hour == 24 and minute):
        raise ValueError(invalid_message)
    return hour * 60 + minute