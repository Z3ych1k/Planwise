"""Scheduling rules, independent of the browser and file system.

This module implements the core task scheduling algorithms, Eisenhower-style
urgency/importance ranking, daily capacity validation, greedy earliest-deadline-first
allocation across a 7-day horizon, and task/work-log state mutations.
"""
from datetime import date, timedelta
import math
import secrets
from validation import parse_date


def minutes(value):
    """Convert an hour string or numeric value into an integer number of minutes.

    Validates that the input is a finite number between 0 and 1000 inclusive,
    aligned to half-hour (0.5-hour) increments.

    Args:
        value (str | int | float): Hour quantity to parse and validate.

    Returns:
        int: The equivalent duration in minutes (e.g., ``1.5`` -> ``90``).

    Raises:
        ValueError: If ``value`` cannot be parsed as a number, is non-finite,
            falls outside ``[0, 1000]``, or is not a multiple of 0.5 hours.
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError('時間請填數字，並以半小時（0.5 小時）為單位。') from None
    # Enforce finite bounds [0, 1000] hours and exact 0.5-hour (30-minute) increments
    if not math.isfinite(number) or not 0 <= number <= 1000 or number * 2 % 1:
        raise ValueError('時間請填 0–1000 小時，並以半小時（0.5 小時）為單位。')
    return int(number * 60)


def rank(task, today):
    """Compute the Eisenhower-matrix priority quadrant index (0 to 3) for a task.

    A task is considered urgent if its kind is ``'deadline'`` and its due date
    is within 3 days of ``today``.

    Args:
        task (dict): Task dictionary containing ``kind``, ``due``, and ``important``.
        today (datetime.date): The reference current date.

    Returns:
        int: Priority rank where ``0`` is urgent & important, ``1`` is non-urgent
        & important, ``2`` is urgent & unimportant, and ``3`` is neither.
    """
    # Quadrant index: 0 = urgent+important, 1 = important, 2 = urgent, 3 = neither
    urgent = task['kind'] == 'deadline' and (date.fromisoformat(task['due']) - today).days <= 3
    return (0 if urgent else 1) if task['important'] else (2 if urgent else 3)


def spent_on(state, day):
    """Calculate total logged work minutes on a specific ISO date.

    Args:
        state (dict): Application state containing the ``work_log`` list.
        day (str): Target date formatted as an ISO-8601 string (``YYYY-MM-DD``).

    Returns:
        int: Sum of ``minutes`` across all work-log entries recorded on ``day``.
    """
    return sum(row['minutes'] for row in state['work_log'] if row['date'] == day)


def schedule(state, today):
    """Allocate active deadline tasks across a 7-day window using greedy EDF.

    Sorts incomplete deadline tasks by due date, importance, and ID, then fills
    available daily capacity between each task's earliest start date and due date.
    Unallocated minutes are classified by failure reason.

    Args:
        state (dict): Application state containing ``capacity``, ``work_log``,
            and ``tasks``.
        today (datetime.date): Start date of the 7-day scheduling horizon.

    Returns:
        tuple[dict[str, list[tuple[dict, int]]], dict[str, int], list[tuple[dict, int, str]]]:
        A 3-tuple ``(plan, free, missing)`` where:
            - ``plan`` maps each ISO date to a list of ``(task, allocated_minutes)`` pairs.
            - ``free`` maps each ISO date to remaining unallocated minutes.
            - ``missing`` lists ``(task, unscheduled_minutes, reason)`` tuples where
              ``reason`` is ``'overdue'``, ``'outside_week'``, or ``'deadline_capacity'``.
    """
    days = [(today + timedelta(days=i)).isoformat() for i in range(7)]
    free = {day: max(0, state['capacity'].get(day, 0) - spent_on(state, day)) for day in days}
    plan = {day: [] for day in days}
    missing = []
    tasks = [task for task in state['tasks'] if task['kind'] == 'deadline' and not task['completed']]
    # shortcut: earliest-deadline-first greedy allocation; no guarantee of a globally optimal plan.
    for task in sorted(tasks, key=lambda item: (item['due'], not item['important'], item['id'])):
        left = task['minutes']
        for day in days:
            if max(days[0], task['start'] or days[0]) <= day <= task['due']:
                take = min(left, free[day])
                if take:
                    plan[day].append((task, take))
                    free[day] -= take
                    left -= take
        # Classify unscheduled minutes into overdue, beyond 7-day horizon, or insufficient capacity
        if left:
            reason = 'overdue' if task['due'] < days[0] else ('outside_week' if task['due'] > days[-1] else 'deadline_capacity')
            missing.append((task, left, reason))
    return plan, free, missing


def suggestions(state, day, free):
    """Recommend incomplete long-term goal tasks when a day has spare capacity.

    Args:
        state (dict): Application state containing the ``tasks`` list.
        day (str): Target ISO date string (``YYYY-MM-DD``) being evaluated.
        free (int): Remaining unallocated capacity in minutes on ``day``.

    Returns:
        list[dict]: Incomplete ``'goal'`` tasks eligible on or before ``day``,
        sorted by importance first and title alphabetically; empty list if
        ``free < 30``.
    """
    # Require at least one 30-minute slot of free capacity before recommending goals
    if free < 30:
        return []
    return sorted((t for t in state['tasks'] if t['kind'] == 'goal' and not t['completed'] and (not t['start'] or t['start'] <= day)), key=lambda t: (not t['important'], t['title']))


def mutate(state, data, today):
    """Apply a user state mutation for capacity updates, task CRUD, or work logging.

    Dispatches based on ``data['action']`` (``'capacity'``, ``'save'``, ``'progress'``,
    or ``'delete'``) and enforces all domain validation rules.

    Args:
        state (dict): Mutable application state containing ``capacity``, ``tasks``,
            and ``work_log``.
        data (dict[str, list[str]]): Parsed form submission mapping field names to
            lists of string values.
        today (datetime.date): Reference date used for the 7-day capacity window
            and work-log timestamps.

    Returns:
        None

    Raises:
        ValueError: If the action is unknown, daily capacity or cumulative logged
            hours exceed 24 hours (1440 minutes), required task fields are missing
            or exceed length limits, date ordering is invalid, or a referenced task
            cannot be found or is already completed.
    """
    def field(key):
        return data.get(key, [''])[0].strip()

    action = field('action')
    # Branch 1: update daily capacity budgets across the 7-day planning window
    if action == 'capacity':
        updated = {}
        for i in range(7):
            day = (today + timedelta(days=i)).isoformat()
            value = minutes(field(day))
            if value > 1440:
                raise ValueError('每天的總可用時間不能超過 24 小時。')
            updated[day] = value
        state['capacity'].update(updated)
        return

    task = next((t for t in state['tasks'] if t['id'] == field('id')), None)
    # Branch 2: create a new deadline/goal task or update an existing active task
    if action == 'save':
        title, course, kind = field('title'), field('course'), field('kind')
        if not title or len(title) > 100 or len(course) > 60:
            raise ValueError('請填寫任務名稱（最多 100 字）；分類最多 60 字。')
        if kind not in ('deadline', 'goal') or field('important') not in ('yes', 'no'):
            raise ValueError('請選擇任務類型及重要程度。')
        start, due = field('start'), field('due') if kind == 'deadline' else ''
        if start:
            start = parse_date(start).isoformat()
        if kind == 'deadline':
            if not due:
                raise ValueError('有 DDL 的任務需要截止日期。長期目標可不填期限。')
            due = parse_date(due).isoformat()
            if start and start > due:
                raise ValueError('最早開始日不能晚於截止日期。')
        amount = minutes(field('hours')) if kind == 'deadline' else 0
        if kind == 'deadline' and amount <= 0:
            raise ValueError('有 DDL 的任務至少需要半小時。')
        if field('id') and task is None:
            raise ValueError('找不到這份任務。')
        if task and task['completed']:
            raise ValueError('這份任務已完成。')
        target = minutes(field('target_hours') or '10') if kind == 'goal' else 600
        if target < 30:
            raise ValueError('圓點參考工時至少半小時。')
        values = dict(target_minutes=target, title=title, course=course, kind=kind, start=start, due=due, minutes=amount, important=field('important') == 'yes')
        if task is None:
            state['tasks'].append(dict(id=secrets.token_hex(8), completed=False, completed_on='', **values))
        else:
            task.update(values)
    # Branch 3: delete a task or record actual effort against an active task
    elif action in ('progress', 'delete'):
        if task is None:
            raise ValueError('找不到這份任務。')
        if action == 'delete':
            state['tasks'].remove(task)
            return
        if task['completed']:
            raise ValueError('這份任務已完成，不能重複記錄。')
        actual = minutes(field('actual'))
        if actual <= 0 or actual + spent_on(state, today.isoformat()) > 1440:
            raise ValueError('本次投入至少半小時；當日累計不能超過 24 小時。')
        finished = field('finished') == 'yes'
        # Goals only complete when explicitly marked finished; deadlines also complete when remaining minutes hit 0
        if task['kind'] == 'deadline':
            task['minutes'] = 0 if finished else max(0, task['minutes'] - actual)
            finished = finished or task['minutes'] == 0
        task['completed'] = finished
        task['completed_on'] = today.isoformat() if finished else ''
        state['work_log'].append(dict(task_id=task['id'], title=task['title'], date=today.isoformat(), minutes=actual, finished=finished))
    else:
        raise ValueError('未知操作。')


def goal_progress(state, task):
    """Compute cumulative invested minutes and completion ratio for a goal task.

    Args:
        state (dict): Application state containing the ``work_log`` list.
        task (dict): Goal task dictionary containing ``id`` and optional
            ``target_minutes`` (defaults to ``600``).

    Returns:
        tuple[int, int, float]: A 3-tuple ``(invested, target, ratio)`` where
        ``invested`` is total logged minutes for the task, ``target`` is the
        reference target minutes, and ``ratio`` is clamped to ``[0.0, 1.0]``.
    """
    invested = sum(row['minutes'] for row in state['work_log'] if row['task_id'] == task['id'])
    target = task.get('target_minutes', 600)
    return invested, target, min(1, invested / target)