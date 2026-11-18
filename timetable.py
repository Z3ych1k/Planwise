"""Half-hour clock slots and explicit approval of earlier task moves.

This module manages fine-grained 30-minute timetable grid scheduling, candidate
plan generation with pinned blocks and private-time borrowing, move-proposal
diffing and user confirmation, custom daily availability windows, and interactive
drag-and-drop block rescheduling.
"""
from datetime import date, timedelta
import secrets
from events import event_cells
from time_slots import TIMETABLE_INVALID_TIME, TIMETABLE_MISSING_TIME, parse_clock


def clock(value):
    """Parse a timetable ``HH:MM`` string into minutes since midnight.

    Args:
        value (str): Time string in ``HH:MM`` format (e.g., ``"18:00"`` or ``"18:30"``).

    Returns:
        int: Minutes elapsed since ``00:00``.

    Raises:
        ValueError: If ``value`` is missing, malformed, or not aligned to 30 minutes.
    """
    return parse_clock(value, TIMETABLE_MISSING_TIME, TIMETABLE_INVALID_TIME)


def stamp(value):
    """Format an integer minute offset from midnight into an ``HH:MM`` string.

    Args:
        value (int): Minutes elapsed since ``00:00`` (e.g., ``570``).

    Returns:
        str: Zero-padded 24-hour clock string (e.g., ``"09:30"``).
    """
    return f'{value // 60:02}:{value % 60:02}'


def day_windows(state, day):
    """Retrieve available ``[start, end]`` minute intervals for a given date.

    Returns the full day ``[[0, 1440]]`` under the ``'free'`` time model, explicit
    configured windows when present in ``state['availability']``, or a default
    evening window ending at ``24:00`` (or ``18:00`` start) derived from ``capacity``.

    Args:
        state (dict): Application state containing ``time_model``, ``availability``,
            and ``capacity``.
        day (str): Target ISO date string (``YYYY-MM-DD``).

    Returns:
        list[list[int]]: List of ``[start_minute, end_minute]`` intervals for ``day``.
    """
    if state.get('time_model') == 'free':
        return [[0, 1440]]
    if day in state.get('availability', {}):
        return state['availability'][day]
    amount = state['capacity'].get(day, 0)
    begin = min(18 * 60, 1440 - amount)
    return [[begin, begin + amount]] if amount else []


def occupied(state, day):
    """Compute the set of 30-minute slot start offsets already logged on a date.

    Uses explicit ``start``/``end`` timestamps when recorded in ``work_log``, and
    falls back to allocating legacy duration-only entries from the start of the
    day's availability window.

    Args:
        state (dict): Application state containing ``work_log``, ``availability``,
            and ``capacity``.
        day (str): Target ISO date string (``YYYY-MM-DD``).

    Returns:
        set[int]: Minute offsets (multiples of 30) already occupied by logged work.
    """
    cells = set()
    legacy_windows = state.get('availability', {}).get(day)
    if legacy_windows is None:
        amount = state['capacity'].get(day, 0)
        begin = min(1080, 1440 - amount)
        legacy_windows = [[begin, begin + amount]] if amount else []
    fallback = [minute for a, b in legacy_windows for minute in range(a, b, 30)]
    for row in state['work_log']:
        if row['date'] != day:
            continue
        if 'start' in row:
            cells.update(range(row['start'], row['end'], 30))
        else:
            # shortcut: v2 recorded daily totals only; place them at the beginning of availability.
            candidates = [minute for minute in fallback if minute not in cells]
            cells.update(candidates[:row['minutes'] // 30])
    return cells


def available_cells(state, today, not_before=0, include_private=False):
    """Collect all schedulable 30-minute ``(date, minute)`` cells across 7 days.

    Excludes slots already logged in ``work_log``, slots blocked by fixed events
    (and private events unless ``include_private`` is ``True``), and slots earlier
    than ``not_before`` on ``today``.

    Args:
        state (dict): Application state dictionary.
        today (datetime.date): First date of the 7-day planning horizon.
        not_before (int, optional): Earliest schedulable minute offset on ``today``.
            Defaults to ``0``.
        include_private (bool, optional): Whether private event slots may be used
            for task scheduling. Defaults to ``False``.

    Returns:
        set[tuple[str, int]]: Available ``(iso_date, start_minute)`` grid cells.
    """
    result = set()
    blocked = event_cells(state, today, 'fixed')
    if not include_private:
        blocked |= event_cells(state, today, 'private')
    for i in range(7):
        day = (today + timedelta(days=i)).isoformat()
        used = occupied(state, day)
        for begin, end in day_windows(state, day):
            result.update((day, t) for t in range(begin, end, 30) if t not in used and (day, t) not in blocked and (i or t >= not_before))
    return result


def may_borrow(state, task, today):
    """Check whether an urgent deadline task is allowed to borrow private event time.

    Args:
        state (dict): Application state containing the ``borrow_private`` flag.
        task (dict): Deadline task dictionary with a ``due`` ISO date string.
        today (datetime.date): Reference current date.

    Returns:
        bool: ``True`` if ``borrow_private`` is enabled and ``task['due']`` falls
        within ``today`` through ``today + 3 days`` inclusive; ``False`` otherwise.
    """
    return state.get('borrow_private', False) and today.isoformat() <= task['due'] <= (today + timedelta(days=3)).isoformat()


def task_cells(state, task, today, not_before=0):
    """Return all valid 30-minute cells where a specific task may be placed.

    Filters ``available_cells`` to the task's ``[start, due]`` date bounds and
    enables private-slot borrowing if ``may_borrow()`` applies.

    Args:
        state (dict): Application state dictionary.
        task (dict): Task dictionary with ``start`` and ``due`` fields.
        today (datetime.date): Start date of the 7-day horizon.
        not_before (int, optional): Earliest allowed minute offset on ``today``.
            Defaults to ``0``.

    Returns:
        set[tuple[str, int]]: Eligible ``(iso_date, start_minute)`` cells for ``task``.
    """
    return {cell for cell in available_cells(state, today, not_before, include_private=may_borrow(state, task, today)) if max(today.isoformat(), task['start'] or today.isoformat()) <= cell[0] <= task['due']}


def cells(blocks):
    """Expand contiguous calendar blocks into a mapping of 30-minute cells to task IDs.

    Args:
        blocks (list[dict]): List of block dictionaries containing ``task_id``,
            ``date``, ``start``, and ``end``.

    Returns:
        dict[tuple[str, int], str]: Mapping from ``(iso_date, start_minute)`` to ``task_id``.
    """
    return {(b['date'], m): b['task_id'] for b in blocks for m in range(b['start'], b['end'], 30)}


def blocks_from_cells(mapping):
    """Merge adjacent 30-minute cells belonging to the same task into contiguous blocks.

    Args:
        mapping (dict[tuple[str, int], str]): Mapping from ``(iso_date, start_minute)``
            to ``task_id``.

    Returns:
        list[dict]: Sorted list of merged block dictionaries with keys ``task_id``,
        ``date``, ``start``, and ``end``.
    """
    blocks = []
    for (day, minute), ident in sorted(mapping.items()):
        if blocks and blocks[-1]['date'] == day and blocks[-1]['task_id'] == ident and blocks[-1]['end'] == minute:
            blocks[-1]['end'] += 30
        else:
            blocks.append(dict(task_id=ident, date=day, start=minute, end=minute + 30))
    return blocks


def candidate(state, today, not_before=0):
    """Build a candidate 7-day timetable schedule honoring pinned blocks and EDF priority.

    First locks in valid user-pinned cells, then allocates remaining deadline
    tasks in earliest-deadline-first order, borrowing private event slots for
    urgent tasks if needed, and records any unscheduled shortfall.

    Args:
        state (dict): Application state dictionary.
        today (datetime.date): Start date of the 7-day scheduling window.
        not_before (int, optional): Earliest schedulable minute on ``today``.
            Defaults to ``0``.

    Returns:
        tuple[list[dict], list[tuple[dict, int, str]]]: A 2-tuple ``(blocks, missing)``
        where ``blocks`` is the merged schedule list and ``missing`` is a list of
        ``(task, unscheduled_minutes, reason)`` tuples.
    """
    free = available_cells(state, today, not_before)
    result, missing = {}, []
    tasks = [t for t in state['tasks'] if t['kind'] == 'deadline' and not t['completed']]
    remaining = {t['id']: t['minutes'] // 30 for t in tasks}
    by_id = {t['id']: t for t in tasks}
    for block in state.get('pins', []):
        task = by_id.get(block['task_id'])
        if not task:
            continue
        allowed = task_cells(state, task, today, not_before)
        for cell in sorted(cells([block])):
            if cell in allowed and cell not in result and remaining[task['id']] > 0:
                result[cell] = task['id']
                free.discard(cell)
                remaining[task['id']] -= 1
    for task in sorted(tasks, key=lambda t: (t['due'], not t['important'], t['id'])):
        eligible = sorted(cell for cell in free if max(today.isoformat(), task['start'] or today.isoformat()) <= cell[0] <= task['due'])
        chosen = eligible[:remaining[task['id']]]
        for cell in chosen:
            result[cell] = task['id']
            free.remove(cell)
        left = (remaining[task['id']] - len(chosen)) * 30
        if left and may_borrow(state, task, today):
            extra = sorted(task_cells(state, task, today, not_before).difference(result))[:left // 30]
            for cell in extra:
                result[cell] = task['id']
                free.discard(cell)
            left -= len(extra) * 30
        if left:
            end = (today + timedelta(days=6)).isoformat()
            reason = 'overdue' if task['due'] < today.isoformat() else ('outside_week' if task['due'] > end else 'deadline_capacity')
            missing.append((task, left, reason))
    return blocks_from_cells(result), missing


def clean_calendar(state, today, not_before=0):
    """Prune stale, completed, or out-of-bounds blocks from the existing calendar.

    Args:
        state (dict): Application state containing ``calendar`` and ``tasks``.
        today (datetime.date): Start date of the 7-day horizon.
        not_before (int, optional): Earliest valid minute on ``today``. Defaults to ``0``.

    Returns:
        list[dict]: Cleaned and merged calendar blocks still valid for active tasks.
    """
    free = available_cells(state, today, not_before, include_private=True)
    tasks = {t['id']: t for t in state['tasks'] if t['kind'] == 'deadline' and not t['completed']}
    left = {ident: t['minutes'] for ident, t in tasks.items()}
    result = {}
    for cell, ident in sorted(cells(state.get('calendar', [])).items()):
        task = tasks.get(ident)
        if task and cell in free and cell in task_cells(state, task, today, not_before) and left[ident] >= 30:
            result[cell] = ident
            free.remove(cell)
            left[ident] -= 30
    return blocks_from_cells(result)


def refresh(state, today, propose=False, not_before=0):
    """Recompute the active timetable and optionally stage a move proposal for approval.

    Prunes invalid pins, generates the optimal candidate schedule ``after``, and
    either applies it immediately (``propose=False``) or preserves existing slots
    while storing ``after`` in ``state['proposal']`` when existing tasks would move.

    Args:
        state (dict): Mutable application state dictionary.
        today (datetime.date): Reference current date.
        propose (bool, optional): If ``True``, keep existing accepted placements
            and create an approval proposal when tasks are shifted. Defaults to ``False``.
        not_before (int, optional): Earliest schedulable minute on ``today``.
            Defaults to ``0``.

    Returns:
        None
    """
    valid = {}
    tasks = {t['id']: t for t in state['tasks'] if t['kind'] == 'deadline' and not t['completed']}
    for cell, ident in cells(state.get('pins', [])).items():
        if ident in tasks and cell in task_cells(state, tasks[ident], today, not_before):
            valid[cell] = ident
    state['pins'] = blocks_from_cells(valid)
    after, _ = candidate(state, today, not_before)
    if propose:
        before = clean_calendar(state, today, not_before)
        # Existing accepted slots come first. Allocate only missing work into the gaps.
        stable = dict(state, pins=before)
        before, _ = candidate(stable, today, not_before)
        state['calendar'] = before
        old, new = cells(before), cells(after)
        moved = {ident for cell, ident in new.items() if old.get(cell) != ident and ident in old.values()}
        state['proposal'] = dict(id=secrets.token_hex(8), date=today.isoformat(), after=after) if moved else None
    else:
        state['calendar'] = after
        state['proposal'] = None
    state['calendar_day'] = today.isoformat()
    state['calendar_model'] = 'events-v4'


def initialize(state, today, not_before=0):
    """Ensure the calendar is initialized or rolled forward for ``today``.

    Triggers ``refresh()`` whenever ``calendar_day`` differs from ``today`` or
    the stored ``calendar_model`` is outdated.

    Args:
        state (dict): Mutable application state dictionary.
        today (datetime.date): Current date.
        not_before (int, optional): Earliest schedulable minute on ``today``.
            Defaults to ``0``.

    Returns:
        None
    """
    if state.get('calendar_day') != today.isoformat() or state.get('calendar_model') != 'events-v4':
        refresh(state, today, propose=bool(state.get('calendar_day')), not_before=not_before)


def decide(state, decision, revision, today):
    """Apply or dismiss a pending timetable move proposal.

    Args:
        state (dict): Mutable application state dictionary.
        decision (str): User action, either ``'confirm_move'`` or ``'keep_plan'``.
        revision (str): Expected proposal ID matching ``state['proposal']['id']``.
        today (datetime.date): Current date used to verify proposal freshness.

    Returns:
        None

    Raises:
        ValueError: If no matching current-day proposal exists or ``decision`` is invalid.
    """
    proposal = state.get('proposal')
    if not proposal or proposal['id'] != revision or proposal['date'] != today.isoformat():
        raise ValueError('前移建議已更新，請重新整理後再確認。')
    if decision == 'confirm_move':
        state['calendar'] = proposal['after']
    elif decision != 'keep_plan':
        raise ValueError('未知的排程選擇。')
    state['proposal'] = None


def update_windows(state, data, today):
    """Update custom daily availability windows (up to 2 intervals per day) for 7 days.

    Switches ``state['time_model']`` to ``'custom'`` and recalculates daily
    total minutes in ``state['capacity']``.

    Args:
        state (dict): Mutable application state dictionary.
        data (dict[str, list[str]]): Form payload containing ``{date}_start_{0|1}``
            and ``{date}_end_{0|1}`` fields.
        today (datetime.date): Start date of the 7-day configuration horizon.

    Returns:
        None

    Raises:
        ValueError: If a window's end time is not after its start time, or two
            windows on the same day overlap.
    """
    updates = {}
    for i in range(7):
        day = (today + timedelta(days=i)).isoformat()
        windows = []
        for index in range(2):
            a = data.get(f'{day}_start_{index}', [''])[0]
            b = data.get(f'{day}_end_{index}', [''])[0]
            if not a and not b:
                continue
            begin, end = clock(a), clock(b)
            if begin >= end:
                raise ValueError('時段結束必須晚於開始。休息日請留空。')
            windows.append([begin, end])
        windows.sort()
        if any(a[1] > b[0] for a, b in zip(windows, windows[1:])):
            raise ValueError('同一天的可用時段不能重疊。')
        updates[day] = windows
    state.setdefault('availability', {}).update(updates)
    state['time_model'] = 'custom'
    for day, windows in updates.items():
        state['capacity'][day] = sum(b - a for a, b in windows)


def record_clock(state, data, today):
    """Validate clock information before ``planner.mutate`` records actual effort.

    Ensures the logged session starts at a valid 30-minute mark, lasts at least
    30 minutes, does not cross midnight, and does not overlap previously logged
    slots on ``today``.

    Args:
        state (dict): Application state dictionary.
        data (dict[str, list[str]]): Form payload containing ``session_start`` and ``actual``.
        today (datetime.date): Current date on which work is being logged.

    Returns:
        tuple[int, int]: A 2-tuple ``(begin, end)`` of minute offsets from midnight.

    Raises:
        ValueError: If duration is non-positive, crosses midnight (``> 1440``),
            or overlaps an already occupied slot on ``today``.
    """
    from planner import minutes
    begin = clock(data.get('session_start', [''])[0])
    amount = minutes(data.get('actual', [''])[0])
    end = begin + amount
    if amount <= 0 or end > 1440:
        raise ValueError('實際投入至少半小時，且不能跨過午夜。')
    if occupied(state, today.isoformat()).intersection(range(begin, end, 30)):
        raise ValueError('這段時間已記錄過投入，請檢查開始時間。')
    return begin, end


def preview_parts(state):
    """Partition current and proposed schedules into unchanged, removed, and added blocks.

    Args:
        state (dict): Application state containing ``calendar`` and optional ``proposal``.

    Returns:
        tuple[list[dict], list[dict], list[dict]]: A 3-tuple ``(same, removed, added)``
        of merged block lists for visual diff rendering; returns ``(calendar, [], [])``
        when no proposal is pending.
    """
    old = cells(state.get('calendar', []))
    proposal = state.get('proposal')
    if not proposal:
        return state.get('calendar', []), [], []
    new = cells(proposal['after'])
    same = {cell: ident for cell, ident in old.items() if new.get(cell) == ident}
    removed = {cell: ident for cell, ident in old.items() if new.get(cell) != ident}
    added = {cell: ident for cell, ident in new.items() if old.get(cell) != ident}
    return blocks_from_cells(same), blocks_from_cells(removed), blocks_from_cells(added)


def move_block(state, data, today, not_before=0):
    """Move a scheduled task block to a new date/time slot and pin its new position.

    Validates that the source block exists, the target slot does not cross midnight,
    all destination cells fall within the task's eligible cells, and no other task
    occupies the target interval.

    Args:
        state (dict): Mutable application state dictionary.
        data (dict[str, list[str]]): Drag-and-drop payload containing ``id``,
            ``source_date``, ``source_start``, ``source_end``, ``new_date``, and ``new_start``.
        today (datetime.date): Start date of the 7-day planning horizon.
        not_before (int, optional): Earliest schedulable minute on ``today``.
            Defaults to ``0``.

    Returns:
        None

    Raises:
        ValueError: If payload fields are malformed, the source block is stale,
            the task is missing or completed, the move crosses midnight, or the
            destination conflicts with events, task bounds, or other scheduled tasks.
    """
    def field(key):
        return data.get(key, [''])[0]

    try:
        source = dict(task_id=field('id'), date=date.fromisoformat(field('source_date')).isoformat(), start=clock(field('source_start')), end=clock(field('source_end')))
        new_day = date.fromisoformat(field('new_date')).isoformat()
        begin = clock(field('new_start'))
    except (ValueError, TypeError):
        raise ValueError('拖動時段不正確。') from None
    if source not in state.get('calendar', []):
        raise ValueError('這段安排已更新，請重新整理後再拖動。')
    task = next((t for t in state['tasks'] if t['id'] == source['task_id'] and not t['completed']), None)
    if task is None:
        raise ValueError('找不到這份待做任務。')
    length = source['end'] - source['start']
    if begin + length > 1440:
        raise ValueError('任務不能拖過午夜；可先分成較短時段。')
    old = cells(state['calendar'])
    source_cells = set(cells([source]))
    new_cells = {(new_day, m) for m in range(begin, begin + length, 30)}
    if not new_cells.issubset(task_cells(state, task, today, not_before)):
        raise ValueError('這裡有固定事項、受保護私人時間，或超出任務期限／可規劃範圍。')
    if new_cells.intersection(set(old) - source_cells):
        raise ValueError('這段時間已有其他任務，請選擇空檔。')
    mapping = {cell: ident for cell, ident in old.items() if cell not in source_cells}
    mapping.update({cell: task['id'] for cell in new_cells})
    state['calendar'] = blocks_from_cells(mapping)
    pins = {cell: ident for cell, ident in cells(state.get('pins', [])).items() if cell not in source_cells}
    pins.update({cell: task['id'] for cell in new_cells})
    state['pins'] = blocks_from_cells(pins)