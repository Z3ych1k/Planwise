"""Validate external form values before business rules read their first item."""
from datetime import date
import math


def normalize_fields(fields):
    """Keep multiple values only for weekday selections; reject ambiguous scalars."""
    if not isinstance(fields, dict) or len(fields) > 100:
        raise ValueError('表單欄位格式不正確。')
    data = {}
    for key, value in fields.items():
        values = value if isinstance(value, list) else [value]
        multiple = key in ('workdays', 'weekdays')
        if (not isinstance(key, str) or len(key) > 100 or len(values) > 20
                or (not multiple and len(values) != 1)):
            raise ValueError('單值欄位必須提供一個值；日期選項才可提供多個值。')
        if any(type(v) not in (str, int, float)
               or (isinstance(v, float) and not math.isfinite(v)) for v in values):
            raise ValueError('表單欄位只能包含文字或有限數字。')
        data[key] = [str(v) for v in values]
    return data


def parse_date(value):
    """Convert user dates without exposing Python's parsing diagnostics."""
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        raise ValueError('日期無效，請輸入有效日期，例如 2026-11-14。') from None
