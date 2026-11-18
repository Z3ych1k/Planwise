"""Fixed appointments and protected personal time, expanded only for the visible dates.

This module manages recurring and single-instance calendar events (fixed appointments
and private time blocks), handles schedule overrides (rescheduling and cancellations),
expands visible occurrences across overnight boundaries, and validates event schemas.
"""
from datetime import date, timedelta
import secrets
from holidays import is_workday
from time_slots import (EVENT_INVALID_TIME, EVENT_MISSING_TIME,
                        TIMETABLE_INVALID_TIME, TIMETABLE_MISSING_TIME, parse_clock)


def clock(value):
    """Parse an event clock string into minutes from midnight.

    Args:
        value (str): A time string in ``HH:MM`` format (e.g., ``"09:30"`` or ``"24:00"``).

    Returns:
        int: The number of minutes elapsed since ``00:00``.

    Raises:
        ValueError: If the time string is missing or improperly formatted.
    """
    return parse_clock(value, EVENT_MISSING_TIME, EVENT_INVALID_TIME)


def matches(event, day, workdays=(0, 1, 2, 3, 4)):
    """Determine whether a recurring or single event occurs on a specific date.

    Evaluates the event's start date, optional ``until`` boundary, and recurrence
    rule (``none``, ``daily``, ``weekly``, ``monthly``, ``workdays``, or ``holidays``).

    Args:
        event (dict): The event dictionary containing ``date``, ``until``, ``repeat``,
            and ``weekdays`` fields.
        day (datetime.date): The candidate date to check against the recurrence rule.
        workdays (Sequence[int], optional): Weekday indices (0=Mon to 6=Sun) treated
            as standard workdays. Defaults to ``(0, 1, 2, 3, 4)``.

    Returns:
        bool: ``True`` if the event falls on ``day`` according to its rule;
        ``False`` otherwise.
    """
    origin = date.fromisoformat(event['date'])
    if day < origin or (event['until'] and day > date.fromisoformat(event['until'])):
        return False
    rule = event['repeat']
    if rule in ('workdays', 'holidays'):
        return is_workday(day, workdays) == (rule == 'workdays')
    return (day == origin if rule == 'none' else True if rule == 'daily' else day.weekday() in event['weekdays'] if rule == 'weekly' else day.day == origin.day)


def occurrences(state, first, last):
    """Expand all active events into concrete time blocks within a visible date range.

    Applies single-instance overrides (reschedules or cancellations) and splits
    overnight events extending past midnight (1440 minutes) into two adjacent daily
    segments so they render cleanly on the calendar grid.

    Args:
        state (dict): Application state containing ``events`` and optional ``workdays``.
        first (datetime.date): The inclusive start date of the visible window.
        last (datetime.date): The inclusive end date of the visible window.

    Returns:
        list[dict]: A chronologically sorted list of expanded occurrence dictionaries,
        each containing ``event_id``, ``occurrence_date``, ``date``, ``start``, ``end``,
        ``title``, ``category``, ``whole_start``, ``whole_end``, ``whole_date``, and ``repeat``.
    """
    result = []
    for event in state.get('events', []):
        origins = {first + timedelta(days=i - 1) for i in range((last - first).days + 2)}
        origins.update(date.fromisoformat(key) for key in event['overrides'])
        for origin in sorted(origins):
            if not matches(event, origin, state.get("workdays", [0, 1, 2, 3, 4])):
                continue
            override = event['overrides'].get(origin.isoformat(), {})
            if override.get('cancelled'):
                continue
            day = date.fromisoformat(override.get('date', origin.isoformat()))
            start, end = override.get('start', event['start']), override.get('end', event['end'])
            segments = [(day, start, min(end, 1440))]
            if end > 1440:
                segments.append((day + timedelta(days=1), 0, end - 1440))
            for current, a, b in segments:
                if first <= current <= last and a < b:
                    result.append(dict(event_id=event['id'], occurrence_date=origin.isoformat(), date=current.isoformat(), start=a, end=b, title=event['title'], category=event['category'], whole_start=start, whole_end=end, whole_date=day.isoformat(), repeat=event['repeat']))
    return sorted(result, key=lambda item: (item['date'], item['start'], item['event_id']))


def event_cells(state, today, category):
    """Compute occupied 30-minute grid cells for a given event category over 7 days.

    Args:
        state (dict): Application state containing all scheduled events.
        today (datetime.date): The starting date of the 7-day planning window.
        category (str): Event category filter (``"fixed"`` or ``"private"``).

    Returns:
        set[tuple[str, int]]: A set of ``(iso_date_str, minute_offset)`` pairs
        representing occupied 30-minute time slots.
    """
    return {(block['date'], m) for block in occurrences(state, today, today + timedelta(days=6)) if block['category'] == category for m in range(block['start'], block['end'], 30)}


def save_event(state, data):
    """Create, update, or delete a fixed or private event series from form data.

    Validates title length, category, recurrence rules, date boundaries, overnight
    time ranges, and weekday selections before mutating ``state['events']``.

    Args:
        state (dict): Application state dictionary holding the ``events`` list.
        data (dict[str, list[str]]): Parsed HTTP form payload mapping field names
            to lists of string values.

    Returns:
        None

    Raises:
        ValueError: If the target event ID is not found, required fields are missing
            or invalid, ``until`` precedes ``date``, start/end times are identical,
            or weekday indices are out of range.
    """
    def field(key):
        return data.get(key, [''])[0].strip()

    ident = field('id')
    old = next((e for e in state['events'] if e['id'] == ident), None)
    if ident and old is None:
        raise ValueError('找不到這個事項。')
    if field('action') == 'delete_event':
        if old is None:
            raise ValueError('找不到這個事項。')
        state['events'].remove(old)
        return
    title, category, rule = field('title'), field('category'), field('repeat')
    if not title or len(title) > 100 or category not in ('fixed', 'private') or rule not in ('none', 'daily', 'weekly', 'monthly', 'workdays', 'holidays'):
        raise ValueError('請填寫事項名稱，並選擇正確的類型及重複規則。')
    day = date.fromisoformat(field('date')).isoformat()
    until = date.fromisoformat(field('until')).isoformat() if field('until') else ''
    if until and until < day:
        raise ValueError('重複結束日期不能早於開始日期。')
    begin, end = clock(field('event_start')), clock(field('event_end'))
    if begin >= 1440 or end == begin:
        raise ValueError('開始與結束時間不能相同；全天請使用 00:00–24:00。')
    if end < begin:
        end += 1440
    try:
        weekdays = sorted({int(v) for v in data.get('weekdays', [])})
    except ValueError:
        raise ValueError('每週重複日期不正確。') from None
    if not weekdays:
        weekdays = [date.fromisoformat(day).weekday()]
    if any(not 0 <= v <= 6 for v in weekdays):
        raise ValueError('每週重複日期不正確。')
    cancelled = {key: row for key, row in old['overrides'].items() if row.get('cancelled')} if old else {}
    values = dict(title=title, category=category, date=day, start=begin, end=end, repeat=rule, until=until, weekdays=weekdays, overrides=cancelled)
    if old is None:
        state['events'].append(dict(id=secrets.token_hex(8), **values))
    else:
        old.update(values)


def move_occurrence(state, data, today):
    """Reschedule a single occurrence of a private event within the 7-day window.

    Records a date/time override keyed by the original occurrence date while
    preserving the event's original duration. Fixed events cannot be moved.

    Args:
        state (dict): Application state dictionary holding the ``events`` list.
        data (dict[str, list[str]]): Form payload containing ``id``,
            ``occurrence_date``, ``new_date``, and ``new_start``.
        today (datetime.date): Reference start date of the 7-day planning horizon.

    Returns:
        None

    Raises:
        ValueError: If the event does not exist, belongs to the ``fixed`` category,
            does not occur on ``occurrence_date``, was already cancelled, or the
            target slot falls outside the valid 7-day window.
    """
    def field(key):
        return data.get(key, [''])[0]

    event = next((e for e in state['events'] if e['id'] == field('id')), None)
    if event is None:
        raise ValueError('找不到這個事項。')
    if event['category'] == 'fixed':
        raise ValueError('固定事項不能移動；如有需要，請編輯整個系列或只移除這一次。')
    original = date.fromisoformat(field('occurrence_date'))
    if not matches(event, original, state.get("workdays", [0, 1, 2, 3, 4])):
        raise ValueError('找不到這一次重複事項。')
    previous = event['overrides'].get(original.isoformat(), {})
    if previous.get('cancelled'):
        raise ValueError('這一次事項已移除。')
    duration = previous.get('end', event['end']) - previous.get('start', event['start'])
    new_day = date.fromisoformat(field('new_date'))
    begin = parse_clock(field('new_start'), TIMETABLE_MISSING_TIME, TIMETABLE_INVALID_TIME)
    if not today <= new_day <= today + timedelta(days=6) or begin >= 1440:
        raise ValueError('請移到未來七天內的有效時段。')
    event['overrides'][original.isoformat()] = dict(date=new_day.isoformat(), start=begin, end=begin + duration)


def cancel_occurrence(state, data):
    """Cancel a single occurrence of an event by its original occurrence date.

    Marks the occurrence as cancelled in ``event['overrides']``, removing both
    halves if the occurrence spans across midnight into the next day.

    Args:
        state (dict): Application state dictionary holding the ``events`` list.
        data (dict[str, list[str]]): Form payload containing ``id`` and
            ``occurrence_date``.

    Returns:
        None

    Raises:
        ValueError: If the event is missing, does not occur on ``occurrence_date``,
            or has already been cancelled.
    """
    event = next((e for e in state['events'] if e['id'] == data.get('id', [''])[0]), None)
    if event is None:
        raise ValueError('找不到這個事項。')
    original = date.fromisoformat(data.get('occurrence_date', [''])[0])
    if not matches(event, original, state.get('workdays', [0, 1, 2, 3, 4])):
        raise ValueError('找不到這一次重複事項。')
    if event['overrides'].get(original.isoformat(), {}).get('cancelled'):
        raise ValueError('這一次事項已移除。')
    event['overrides'][original.isoformat()] = dict(cancelled=True)


def validate_events(items):
    """Validate the structural integrity and field constraints of loaded event records.

    Verifies unique string IDs, title lengths, ISO date formats, category and
    recurrence enums, weekday lists, 30-minute aligned start/end intervals, and
    override dictionaries.

    Args:
        items (list[dict]): Raw list of event dictionaries loaded from storage.

    Returns:
        list[dict]: The validated list of event dictionaries unchanged.

    Raises:
        ValueError: If ``items`` is not a list or any event record or override
            violates schema, type, alignment, or boundary constraints.
    """
    if not isinstance(items, list):
        raise ValueError('固定事項資料不正確。')
    seen = set()
    for e in items:
        if not all(isinstance(e[k], str) for k in ('id', 'title', 'date', 'category', 'repeat', 'until')) or not e['id'] or e['id'] in seen or not e['title'] or len(e['title']) > 100:
            raise ValueError('固定事項名稱或識別碼不正確。')
        seen.add(e['id'])
        origin = date.fromisoformat(e['date'])
        if e['until'] and date.fromisoformat(e['until']) < origin:
            raise ValueError('事項結束日期不正確。')
        if e['category'] not in ('fixed', 'private') or e['repeat'] not in ('none', 'daily', 'weekly', 'monthly', 'workdays', 'holidays'):
            raise ValueError('事項類型或重複規則不正確。')
        if not isinstance(e['weekdays'], list) or not e['weekdays'] or any(type(v) is not int or not 0 <= v <= 6 for v in e['weekdays']):
            raise ValueError('每週重複日期不正確。')

        def check_time(row):
            if any(type(row[k]) is not int or row[k] % 30 for k in ('start', 'end')) or not 0 <= row['start'] < 1440 or not row['start'] < row['end'] <= row['start'] + 1440:
                raise ValueError('事項時段不正確