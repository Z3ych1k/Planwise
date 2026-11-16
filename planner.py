"""Scheduling rules, independent of the browser and file system."""
from datetime import date, timedelta
import math
import secrets
from validation import parse_date


def minutes(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError('時間請填數字，並以半小時（0.5 小時）為單位。') from None
    if not math.isfinite(number) or not 0 <= number <= 1000 or number * 2 % 1:
        raise ValueError('時間請填 0–1000 小時，並以半小時（0.5 小時）為單位。')
    return int(number * 60)


def rank(task, today):
    urgent = task['kind'] == 'deadline' and (date.fromisoformat(task['due']) - today).days <= 3
    return (0 if urgent else 1) if task['important'] else (2 if urgent else 3)


def spent_on(state, day):
    return sum(row['minutes'] for row in state['work_log'] if row['date'] == day)


def schedule(state, today):
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
        if left:
            reason = 'overdue' if task['due'] < days[0] else ('outside_week' if task['due'] > days[-1] else 'deadline_capacity')
            missing.append((task, left, reason))
    return plan, free, missing


def suggestions(state, day, free):
    if free < 30:
        return []
    return sorted((t for t in state['tasks'] if t['kind'] == 'goal' and not t['completed'] and (not t['start'] or t['start'] <= day)), key=lambda t: (not t['important'], t['title']))


def mutate(state, data, today):
    def field(key):
        return data.get(key, [''])[0].strip()

    action = field('action')
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
        target = minutes(field('target_hours') or '10') if kind=='goal' else 600
        if target<30:raise ValueError('圓點參考工時至少半小時。')
        values = dict(target_minutes=target, title=title, course=course, kind=kind, start=start, due=due, minutes=amount, important=field('important') == 'yes')
        if task is None:
            state['tasks'].append(dict(id=secrets.token_hex(8), completed=False, completed_on='', **values))
        else:
            task.update(values)
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
        if task['kind'] == 'deadline':
            task['minutes'] = 0 if finished else max(0, task['minutes'] - actual)
            finished = finished or task['minutes'] == 0
        task['completed'] = finished
        task['completed_on'] = today.isoformat() if finished else ''
        state['work_log'].append(dict(task_id=task['id'], title=task['title'], date=today.isoformat(), minutes=actual, finished=finished))
    else:
        raise ValueError('未知操作。')


def goal_progress(state,task):
    invested=sum(row['minutes'] for row in state['work_log'] if row['task_id']==task['id'])
    target=task.get('target_minutes',600)
    return invested,target,min(1,invested/target)
