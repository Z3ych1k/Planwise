"""Validate and normalize external form payloads and date strings.

This module sanitizes incoming HTTP or JSON form mappings before domain rules
inspect them, enforcing single-value vs. multi-value field constraints, finite
scalar types, and user-friendly ISO-8601 date parsing without leaking raw Python
parser tracebacks.
"""
from datetime import date
import math


def normalize_fields(fields):
    """Normalize incoming form fields into a mapping of string lists.

    Allows multiple values only for ``'workdays'`` and ``'weekdays'`` keys while
    enforcing single-value lists for all other fields, capping dictionary and
    list sizes, and rejecting non-scalar or non-finite values.

    Args:
        fields (dict[str, Any]): Raw form or JSON payload mapping field names
            to scalar values or lists of values.

    Returns:
        dict[str, list[str]]: A sanitized dictionary mapping each field name to
        a list of stringified values.

    Raises:
        ValueError: If ``fields`` is not a dictionary or exceeds 100 entries,
            a key is not a valid string within 100 characters, a single-value
            field receives multiple or zero items, a multi-value field exceeds
            20 items, or any value is not a finite ``str``, ``int``, or ``float``.
    """
    # Guard against non-dict payloads or oversized form submissions
    if not isinstance(fields, dict) or len(fields) > 100:
        raise ValueError('表單欄位格式不正確。')
    data = {}
    for key, value in fields.items():
        values = value if isinstance(value, list) else [value]
        # Only workdays and weekdays checkboxes are permitted to submit multiple values
        multiple = key in ('workdays', 'weekdays')
        if (not isinstance(key, str) or len(key) > 100 or len(values) > 20
                or (not multiple and len(values) != 1)):
            raise ValueError('單值欄位必須提供一個值；日期選項才可提供多個值。')
        # Reject booleans (subclass of int), None, nested structures, and NaN/Inf floats
        if any(type(v) not in (str, int, float)
               or (isinstance(v, float) and not math.isfinite(v)) for v in values):
            raise ValueError('表單欄位只能包含文字或有限數字。')
        data[key] = [str(v) for v in values]
    return data


def parse_date(value):
    """Parse an ISO-8601 date string into a ``datetime.date`` object.

    Wraps ``date.fromisoformat`` to raise a localized, user-friendly ``ValueError``
    instead of exposing low-level Python parsing diagnostics.

    Args:
        value (str): Date string expected in ``YYYY-MM-DD`` format (e.g., ``"2026-11-14"``).

    Returns:
        datetime.date: The parsed calendar date object.

    Raises:
        ValueError: If ``value`` is not a valid ISO-8601 date string or has an
            invalid type.
    """
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        raise ValueError('日期無效，請輸入有效日期，例如 2026-11-14。') from None