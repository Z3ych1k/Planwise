"""Fixed and private calendar events, recurrence expansion, and occurrence overrides.

This module manages fixed commitments and protected private time blocks, supporting
one-time and recurring schedules (``none``, ``daily``, ``weekly``, ``workdays``,
``holidays``, ``monthly``), multi-weekday selection, overnight intervals where
``end > 1440``, single-occurrence moves or cancellations, and schema validation.
"""
from datetime import date, timedelta
import secrets
from holidays import is_workday
from time_slots import (
    EVENT_INVALID_TIME,
    EVENT_MISSING_TIME,
    TIMETABLE_INVALID_TIME,
    TIMETABLE_MISSING_TIME,
    parse_clock,
)
from validation import parse_date


def matches(event, day, workdays=(0, 1, 2, 3, 4)):
    """Check whether an event's recurrence rule triggers on a given date.

    Args:
        event (dict): Event dictionary containing ``date``, ``until``, ``repeat``,
            and optional ``weekdays``.
        day (datetime.date): Target calendar date to test.
        workdays (Sequence[int], optional): Weekday integers (0=Mon .. 6=Sun)
            treated as working days when evaluating ``'workdays'`` and
            ``'holidays'`` recurrence. Defaults to ``(0, 1, 2, 3, 4)``.

    Returns:
        bool: ``True`` if the event occurs on ``day`` within its ``[date, until]``
        active range; ``False`` otherwise.
    """
    origin = date.fromisoformat(event['date'])
    if day < origin:
        return False
    if event.get('until') and day > date.fromisoformat(event['until']):
        return False
    repeat = event.get('repeat', 'none')
    if repeat == 'none':
        return day == origin
    if repeat == 'daily':
        return True
    if repeat == 'weekly':
        days = event.get('weekdays') or [origin.weekday()]
        return day.weekday() in days
    if repeat == 'workdays':
        return is_workday(day, workdays)
    if repeat == 'holidays':
        return not is_workday(day, workdays)
    if repeat == 'monthly':
        return day.day == origin.day
    return False


def occurrences(state, first_day, last_day, category=None):
    """Expand all matching event instances across an inclusive date window.

    Handles single-occurrence date/time overrides, cancelled instances, and
    overnight intervals (``end > 1440``) by splitting them into ``[start, 1440]``
    on day ``D`` and ``[0, end - 1440]`` on day ``D + 1``.

    Args:
        state (dict): Application state containing ``events`` and optional ``workdays``.
        first_day (datetime.date): Inclusive start date of the query window.
        last_day (datetime.date): Inclusive end date of the query window.
        category (str | None, optional): Filter by ``'fixed'`` or ``'private'``,
            or ``None`` to include all categories. Defaults to ``None``.

    Returns:
        list[dict]: Sorted list of expanded occurrence blocks, each containing
        ``event_id``, ``title``, ``category``, ``repeat``, ``date``,
        ``occurrence_date``, ``start``, ``end``, ``movable``, and ``overnight``.
        ``whole_date``, ``whole_start``, and ``whole_end`` describe the unsplit block.
    """
    workdays = state.get('workdays', [0, 1, 2, 3, 4])
    blocks = []
    scan_start = first_day - timedelta(days=1)
    window_origins = {
        scan_start + timedelta(days=i) for i in range((last_day - scan_start).days + 1)
    }
    for event in state.get('events', []):
        if category and event['category'] != category:
            continue
        overrides = event.get('overrides', {})
        # A visible block may have been moved from a date outside this window.
        origins = window_origins | {date.fromisoformat(key) for key in overrides}
        for origin in sorted(origins):
            if not matches(event, origin, workdays):
                continue
            occ_key = origin.isoformat()
            override = overrides.get(occ_key, {})
            if override.get('cancelled'):
                continue
            target_day = date.fromisoformat(override.get('date', occ_key))
            start = override.get('start', event['start'])
            end = override.get('end', event['end'])
            overnight = end > 1440
            segments = [(target_day, start, min(end, 1440))]
            if overnight:
                segments.append((target_day + timedelta(days=1), 0, end - 1440))
            for day, segment_start, segment_end in segments:
                if first_day <= day <= last_day and segment_start < segment_end:
                    blocks.append(dict(
                        event_id=event['id'],
                        title=event['title'],
                        category=event['category'],
                        repeat=event['repeat'],
                        date=day.isoformat(),
                        occurrence_date=occ_key,
                        start=segment_start,
                        end=segment_end,
                        whole_date=target_day.isoformat(),
                        whole_start=start,
                        whole_end=end,
                        movable=event['category'] == 'private',
                        overnight=overnight,
                    ))
    return sorted(blocks, key=lambda b: (b['date'], b['start'], b['event_id']))


def event_cells(state, today, category=None):
    """Collect all 30-minute ``(date, minute)`` grid cells occupied by events in a 7-day window.

    Args:
        state (dict): Application state dictionary.
        today (datetime.date): First date of the 7-day planning horizon.
        category (str | None, optional): Optional category filter (``'fixed'`` or
            ``'private'``). Defaults to ``None``.

    Returns:
        set[tuple[str, int]]: Set of ``(iso_date, start_minute)`` grid cells covered
        by matching event occurrences.
    """
    end_day = today + timedelta(days=6)
    return {
        (block['date'], minute)
        for block in occurrences(state, today, end_day, category=category)
        for minute in range(block['start'], block['end'], 30)
    }


def _parse_weekdays(raw_list, fallback_day):
    """Parse and deduplicate weekday integers ``0..6`` for weekly recurrence.

    Args:
        raw_list (list[str]): Raw form values for ``weekdays``.
        fallback_day (datetime.date): Origin date whose weekday is used if
            ``raw_list`` is empty.

    Returns:
        list[int]: Sorted unique weekday integers in ``0..6``.

    Raises:
        ValueError: If any weekday value is not an integer in ``0..6``.
    """
    if not raw_list:
        return [fallback_day.weekday()]
    days = set()
    for item in raw_list:
        try:
            val = int(item)
        except (TypeError, ValueError):
            raise ValueError('請選擇有效的星期。') from None
        if not 0 <= val <= 6:
            raise ValueError('請選擇有效的星期。')
        days.add(val)
    return sorted(days)


def save_event(state, data):
    """Create, update, or delete a fixed or private event series in application state.

    Dispatches to :func:`delete_event` when ``action == 'delete_event'``. For
    creations and edits, normalizes overnight end times to ``end + 1440`` when
    ``end < start``, validates ``weekdays``, and preserves cancelled dates while
    clearing single-day time moves on series updates.

    Args:
        state (dict): Mutable application state containing ``events``.
        data (dict[str, list[str]]): Normalized form payload containing ``action``,
            ``id``, ``title``, ``category``, ``date``, ``until``, ``event_start``,
            ``event_end``, ``repeat``, and optional ``weekdays``.

    Returns:
        None

    Raises:
        ValueError: If required fields are missing or exceed limits, dates/times
            are malformed, ``until`` precedes ``date``, or an existing ``id`` is
            not found.
    """
    def field(key):
        return data.get(key, [''])[0].strip()

    if field('action') == 'delete_event':
        delete_event(state, data)
        return

    title = field('title')
    if not title or len(title) > 100:
        raise ValueError('請填寫事項名稱（最多 100 字）。')
    category = field('category')
    if category not in ('fixed', 'private'):
        raise ValueError('請選擇事項類型（固定事項或私人時間）。')
    repeat = field('repeat') or 'none'
    if repeat not in ('none', 'daily', 'weekly', 'workdays', 'holidays', 'monthly'):
        raise ValueError('請選擇有效的重複規則。')
    start_day = parse_date(field('date'))
    until_raw = field('until')
    until = ''
    if until_raw:
        until_day = parse_date(until_raw)
        if until_day < start_day:
            raise ValueError('重複結束日期不能早於開始日期。')
        until = until_day.isoformat()
    start = parse_clock(field('event_start'), EVENT_MISSING_TIME, EVENT_INVALID_TIME)
    raw_end = parse_clock(field('event_end'), EVENT_MISSING_TIME, EVENT_INVALID_TIME)
    if start >= 1440 or start == raw_end:
        raise ValueError(EVENT_INVALID_TIME)
    # Encode overnight intervals (e.g. 22:00..06:00) by adding 1440 minutes to end
    end = raw_end + 1440 if raw_end < start else raw_end
    weekdays = _parse_weekdays(data.get('weekdays', []), start_day) if repeat == 'weekly' else []

    ident = field('id')
    existing = next((e for e in state['events'] if e['id'] == ident), None) if ident else None
    if ident and existing is None:
        raise ValueError('找不到這個事項。')

    # Keep single-date cancellations when editing a series, but reset single-occurrence time moves
    preserved_overrides = {}
    if existing is not None:
        preserved_overrides = {
            k: dict(cancelled=True)
            for k, v in existing.get('overrides', {}).items()
            if v.get('cancelled')
        }

    record = dict(
        id=existing['id'] if existing else secrets.token_hex(8),
        title=title,
        category=category,
        date=start_day.isoformat(),
        until=until,
        start=start,
        end=end,
        repeat=repeat,
        weekdays=weekdays,
        overrides=preserved_overrides,
    )
    if existing is None:
        state['events'].append(record)
    else:
        existing.update(record)


def delete_event(state, data):
    """Remove an entire event series from application state by its identifier.

    Args:
        state (dict): Mutable application state containing ``events``.
        data (dict[str, list[str]]): Form payload containing ``id``.

    Returns:
        None

    Raises:
        ValueError: If no event matching ``id`` exists in ``state['events']``.
    """
    ident = data.get('id', [''])[0].strip()
    existing = next((e for e in state['events'] if e['id'] == ident), None)
    if existing is None:
        raise ValueError('找不到這個事項。')
    state['events'].remove(existing)


def move_occurrence(state, data, today):
    """Reschedule a single instance of a private recurring or single event.

    Creates or updates a date-keyed override entry in ``event['overrides']`` while
    preserving the original event duration. Fixed events cannot be moved individually.

    Args:
        state (dict): Application state containing ``events`` and optional ``workdays``.
        data (dict[str, list[str]]): Form payload with ``id``, ``occurrence_date``,
            ``new_date``, and ``new_start``.
        today (datetime.date): The start date of the 7-day planning window; target
            dates must fall within ``[today, today + 6 days]``.

    Returns:
        None

    Raises:
        ValueError: If the event does not exist, belongs to the ``fixed`` category,
            does not occur on ``occurrence_date``, was already cancelled, or targets
            an out-of-range date/time.
    """
    def field(key):
        return data.get(key, [''])[0]

    event = next((e for e in state['events'] if e['id'] == field('id')), None)
    if event is None:
        raise ValueError('找不到這個事項。')
    # Fixed appointments are strictly locked against single-occurrence dragging
    if event['category'] == 'fixed':
        raise ValueError('固定事項不能移動；如有需要，請編輯整個系列或只移除這一次。')
    original = parse_date(field('occurrence_date'))
    if not matches(event, original, state.get("workdays", [0, 1, 2, 3, 4])):
        raise ValueError('找不到這一次重複事項。')
    previous = event['overrides'].get(original.isoformat(), {})
    if previous.get('cancelled'):
        raise ValueError('這一次事項已移除。')
    duration = previous.get('end', event['end']) - previous.get('start', event['start'])
    new_day = parse_date(field('new_date'))
    begin = parse_clock(field('new_start'), TIMETABLE_MISSING_TIME, TIMETABLE_INVALID_TIME)
    # Enforce 7-day scheduling horizon [today, today + 6] and valid start before 24:00
    if not today <= new_day <= today + timedelta(days=6) or begin >= 1440:
        raise ValueError('請移到未來七天內的有效時段。')
    event['overrides'][original.isoformat()] = dict(date=new_day.isoformat(), start=begin, end=begin + duration)


def cancel_occurrence(state, data):
    """Cancel a single occurrence of an event by its original scheduled date.

    Marks the occurrence as ``{'cancelled': True}`` in ``event['overrides']``,
    suppressing both segments if the event spans across midnight.

    Args:
        state (dict): Application state containing ``events`` and optional ``workdays``.
        data (dict[str, list[str]]): Form payload containing ``id`` and
            ``occurrence_date``.

    Returns:
        None

    Raises:
        ValueError: If the event does not exist, does not match ``occurrence_date``,
            or has already been cancelled.
    """
    event = next((e for e in state['events'] if e['id'] == data.get('id', [''])[0]), None)
    if event is None:
        raise ValueError('找不到這個事項。')
    original = parse_date(data.get('occurrence_date', [''])[0])
    if not matches(event, original, state.get('workdays', [0, 1, 2, 3, 4])):
        raise ValueError('找不到這一次重複事項。')
    if event['overrides'].get(original.isoformat(), {}).get('cancelled'):
        raise ValueError('這一次事項已移除。')
    event['overrides'][original.isoformat()] = dict(cancelled=True)


def validate_events(items):
    """Validate and normalize a list of raw event dictionaries from persisted state.

    Enforces schema constraints across event identifiers, titles, categories,
    recurrence rules, weekday lists, half-hour time boundaries (up to ``2880``
    minutes for overnight spans), and date-keyed overrides.

    Args:
        items (list[dict]): Raw event records loaded from JSON storage or backup.

    Returns:
        list[dict]: Validated and normalized event dictionaries.

    Raises:
        ValueError: If ``items`` is not a list, any event has invalid fields,
            duplicate IDs, malformed dates/times, or invalid override entries.
    """
    if not isinstance(items, list):
        raise ValueError('事項格式不正確。')
    result = []
    seen = set()
    for raw in items:
        if not isinstance(raw, dict):
            raise ValueError('事項格式不正確。')
        event = dict(raw)
        ident = event.get('id')
        title = event.get('title')
        if not isinstance(ident, str) or not ident or ident in seen:
            raise ValueError('事項識別碼不正確。')
        if not isinstance(title, str) or not title.strip() or len(title) > 100:
            raise ValueError('事項名稱不正確。')
        if event.get('category') not in ('fixed', 'private'):
            raise ValueError('事項類型不正確。')
        repeat = event.get('repeat')
        if repeat not in ('none', 'daily', 'weekly', 'workdays', 'holidays', 'monthly'):
            raise ValueError('重複規則不正確。')
        start = event.get('start')
        end = event.get('end')
        # Overnight intervals can reach end == 2880 (next-day 24:00) while max duration stays <= 1440 min
        if (type(start) is not int or type(end) is not int
                or start % 30 or end % 30
                or not 0 <= start < 1440 or not 30 <= end <= 2880
                or end <= start or end - start > 1440):
            raise ValueError('事項時間不正確。')
        start_day = date.fromisoformat(event['date'])
        until = event.get('until', '')
        if until:
            until_day = date.fromisoformat(until)
            if until_day < start_day:
                raise ValueError('重複結束日期不能早於開始日期。')
            event['until'] = until_day.isoformat()
        else:
            event['until'] = ''
        event['date'] = start_day.isoformat()

        raw_weekdays = event.get('weekdays', [])
        if not isinstance(raw_weekdays, list) or any(type(d) is not int or not 0 <= d <= 6 for d in raw_weekdays):
            raise ValueError('重複星期不正確。')
        if repeat == 'weekly':
            event['weekdays'] = sorted(set(raw_weekdays)) if raw_weekdays else [start_day.weekday()]
        else:
            event['weekdays'] = sorted(set(raw_weekdays))

        # Validate per-date overrides: either a cancellation flag or a duration-preserving time move
        overrides = event.get('overrides', {})
        if not isinstance(overrides, dict):
            raise ValueError('單次修改格式不正確。')
        clean_overrides = {}
        expected_duration = end - start
        for key, item in overrides.items():
            date.fromisoformat(key)
            if not isinstance(item, dict):
                raise ValueError('單次修改格式不正確。')
            if item.get('cancelled') is True:
                clean_overrides[key] = dict(cancelled=True)
            else:
                new_day = date.fromisoformat(item['date']).isoformat()
                o_start = item.get('start')
                o_end = item.get('end')
                if (type(o_start) is not int or type(o_end) is not int
                        or o_start % 30 or o_end % 30
                        or not 0 <= o_start < 1440
                        or o_end - o_start != expected_duration):
                    raise ValueError('單次修改時段不正確。')
                clean_overrides[key] = dict(date=new_day, start=o_start, end=o_end)
        event['overrides'] = clean_overrides
        seen.add(ident)
        result.append(event)
    return result