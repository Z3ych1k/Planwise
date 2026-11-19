"""Translate the JSON API into the existing scheduling rules."""
from datetime import timedelta

from events import cancel_occurrence, move_occurrence, occurrences, save_event
from holidays import holiday_name, YEARS
from planner import goal_progress, mutate, rank
from storage import import_state
from validation import normalize_fields
from timetable import (available_cells, cells, decide, initialize, preview_parts,
                       record_clock, refresh, move_block, update_windows)


def apply(state, action, fields, today, cutoff):
    data = normalize_fields(fields)
    data['action'] = [action]
    initialize(state, today, cutoff)
    if action == 'import_data':
        if data.get('replace_confirm') != ['yes']:
            raise ValueError('Please confirm replacing your current plan.')
        text = data.get('backup_json', [''])[0]
        imported = import_state(text)
        if any(len(imported[k]) > limit for k, limit in [('tasks', 500), ('events', 500), ('work_log', 5000)]):
            raise ValueError('Backup exceeds the NAS edition limits (500 tasks / 500 events / 5000 logs).')
        state = imported
        initialize(state, today, cutoff)
        return state
    if action == 'save_settings':
        language = data.get('language', [''])[0]
        try:
            workdays = sorted({int(day) for day in data.get('workdays', [])})
        except ValueError:
            raise ValueError('工作日設定不正確。') from None
        if language not in ('zh-Hant', 'zh-Hans', 'en') or any(d not in range(7) for d in workdays):
            raise ValueError('語言或工作日設定不正確。')
        changed = workdays != state['workdays']
        state.update(language=language, workdays=workdays)
        if changed:
            refresh(state, today, propose=True, not_before=cutoff)
    elif action in ('confirm_move', 'keep_plan'):
        decide(state, action, data.get('revision', [''])[0], today)
    else:
        if action == 'move_block':
            move_block(state, data, today, cutoff)
        elif action == 'move_event':
            move_occurrence(state, data, today)
        elif action == 'cancel_occurrence':
            cancel_occurrence(state, data)
        elif action in ('save_event', 'delete_event'):
            save_event(state, data)
        elif action == 'save_policy':
            state['borrow_private'] = data.get('borrow_private') == ['yes']
        elif action == 'windows':
            update_windows(state, data, today)
        elif action == 'full_day':
            state['time_model'] = 'free'
        elif action in ('save', 'delete', 'progress'):
            session = record_clock(state, data, today) if action == 'progress' else None
            mutate(state, data, today)
            if session:
                state['work_log'][-1].update(start=session[0], end=session[1])
        else:
            raise ValueError('Unknown action.')
        refresh(state, today, propose=True, not_before=cutoff)
    if len(state['tasks']) > 500 or len(state['events']) > 500 or len(state['work_log']) > 5000:
        raise ValueError('Plan limit reached; export a backup before archiving old records.')
    return state


def view(state, today, cutoff):
    days = [today + timedelta(days=i) for i in range(7)]
    booked = cells(state['calendar'])
    missing = []
    for task in state['tasks']:
        if task['completed'] or task['kind'] != 'deadline':
            continue
        left = task['minutes'] - 30*sum(ident == task['id'] for ident in booked.values())
        if left > 0:
            reason = 'overdue' if task['due'] < today.isoformat() else 'outside_week' if task['due'] > days[-1].isoformat() else 'deadline_capacity'
            missing.append(dict(id=task['id'], minutes=left, reason=reason))
    same, removed, added = preview_parts(state)
    return dict(today=today.isoformat(), cutoff=cutoff, days=[dict(date=d.isoformat(), holiday=holiday_name(d), weekday=d.weekday()) for d in days],
                holidays_supported=today.year in YEARS,
                occurrences=occurrences(state, days[0], days[-1]),
                available=sorted(available_cells(state, today, cutoff)),
                missing=missing, preview=dict(same=same, removed=removed, added=added),
                ranks={t['id']:rank(t, today) for t in state['tasks']},
                progress={t['id']:goal_progress(state, t) for t in state['tasks'] if t['kind']=='goal'})
