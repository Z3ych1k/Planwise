"""Acceptance checks and boundary tests for the rules in SPEC.md; all data is temporary.

Provides shared test fixtures (``TODAY``, ``D0``, ``D1``, ``task``, ``state``, ``form``)
and verifies task prioritization, greedy EDF scheduling invariants, state mutations,
goal progress clamping, legacy v1-to-v2 migration, atomic persistence, and XSS escaping.
"""
from copy import deepcopy
from datetime import date, timedelta
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from android.runtime.main import Handler, make_server, render
from planner import goal_progress, minutes, mutate, rank, schedule, spent_on, suggestions
from storage import empty_state, load_state, migrate, save_state, seed

TODAY = date(2026, 11, 5)
D0 = TODAY.isoformat()
D1 = (TODAY + timedelta(days=1)).isoformat()


def task(ident='a', delta=2, amount=120, important=True, kind='deadline', start=''):
    """Create a normalized task dictionary for scheduling tests.

    Args:
        ident (str, optional): Task identifier and default title. Defaults to ``'a'``.
        delta (int, optional): Due-date offset in days from ``TODAY``. Defaults to ``2``.
        amount (int, optional): Remaining duration in minutes. Defaults to ``120``.
        important (bool, optional): Importance flag. Defaults to ``True``.
        kind (str, optional): Task type (``'deadline'`` or ``'goal'``).
            Defaults to ``'deadline'``.
        start (str, optional): Earliest start date in ISO format. Defaults to ``''``.

    Returns:
        dict: Task dictionary conforming to the version-2 schema.
    """
    return dict(
        id=ident,
        title=ident,
        course='test',
        kind=kind,
        due=(TODAY + timedelta(days=delta)).isoformat() if kind == 'deadline' else '',
        start=start,
        minutes=amount if kind == 'deadline' else 0,
        important=important,
        completed=False,
        completed_on='',
    )


def state(tasks, capacity=None):
    """Build a custom-time-model application state containing ``tasks`` and ``capacity``.

    Args:
        tasks (list[dict]): List of task dictionaries.
        capacity (dict[str, int] | None, optional): Daily capacity map in minutes.
            Defaults to ``{D0: 120, D1: 120}``.

    Returns:
        dict: Initialized state dictionary ready for scheduler testing.
    """
    result = empty_state()
    result.update(tasks=tasks, capacity=capacity if capacity is not None else {D0: 120, D1: 120})
    result['time_model'] = 'custom'
    return result


def form(**values):
    """Convert keyword arguments into a URL-encoded form payload dictionary.

    Args:
        **values: Form field names mapped to scalar values.

    Returns:
        dict[str, list[str]]: Dictionary mapping each field name to a single-element
        list of stringified values.
    """
    return {key: [str(value)] for key, value in values.items()}


class SchedulingTests(unittest.TestCase):
    """Unit and boundary tests for task ranking, EDF scheduling, and state mutations."""

    def test_urgent_boundary_and_goal(self):
        """Verify the 3-day urgency threshold and Eisenhower quadrant ranking for deadlines and goals."""
        self.assertEqual(rank(task(delta=3), TODAY), 0)
        self.assertEqual(rank(task(delta=4), TODAY), 1)
        self.assertEqual(rank(task(delta=0, important=False), TODAY), 2)
        self.assertEqual(rank(task(kind='goal'), TODAY), 1)

    def test_deadline_prevents_old_priority_conflict(self):
        """Verify an earlier deadline takes precedence over a later important task."""
        s = state([task('A', delta=5, amount=60), task('B', delta=0, amount=60, important=False)], {D0: 60, D1: 60})
        plan, _, missing = schedule(s, TODAY)
        self.assertEqual(plan[D0][0][0]['id'], 'B')
        self.assertEqual(plan[D1][0][0]['id'], 'A')
        self.assertEqual(missing, [])

    def test_equal_deadline_uses_importance(self):
        """Verify importance breaks ties when two tasks share the exact same due date."""
        plan, _, _ = schedule(state([task('a', important=False), task('z', important=True)]), TODAY)
        self.assertEqual(plan[D0][0][0]['id'], 'z')

    def test_today_allowed_overdue_excluded(self):
        """Verify tasks due today are scheduled while already-overdue tasks are flagged as ``'overdue'``."""
        plan, _, missing = schedule(state([task('late', delta=-1), task('today', delta=0)]), TODAY)
        self.assertEqual([t['id'] for t, _ in plan[D0]], ['today'])
        self.assertEqual(missing[0][2], 'overdue')

    def test_missing_reasons_are_distinct(self):
        """Verify unscheduled shortfalls are categorized into ``overdue``, ``deadline_capacity``, and ``outside_week``."""
        _, free, missing = schedule(state([task('past', delta=-1), task('near', delta=1), task('far', delta=20)], {}), TODAY)
        self.assertEqual({t['id']: code for t, _, code in missing}, {'past': 'overdue', 'near': 'deadline_capacity', 'far': 'outside_week'})
        self.assertEqual(sum(free.values()), 0)

    def test_start_date_respected(self):
        """Verify tasks are never scheduled prior to their configured ``start`` date."""
        plan, _, _ = schedule(state([task(start=D1)]), TODAY)
        self.assertEqual(plan[D0], [])
        self.assertEqual(sum(n for _, n in plan[D1]), 120)

    def test_goals_are_reminders_and_start_later(self):
        """Verify long-term goals do not consume fixed capacity and appear in suggestions only from ``start``."""
        goal = task('N1', kind='goal', start=D1)
        s = state([goal])
        plan, free, missing = schedule(s, TODAY)
        self.assertFalse(any(plan.values()))
        self.assertEqual(missing, [])
        self.assertEqual(suggestions(s, D0, free[D0]), [])
        self.assertEqual(suggestions(s, D1, free[D1]), [goal])
        self.assertEqual(suggestions(s, D1, 0), [])

    def test_early_finish_moves_next_task_and_preserves_free_time(self):
        """Verify completing a task early frees remaining capacity for subsequent tasks while keeping spent logs."""
        s = state([task('A', delta=0), task('B', delta=1, amount=60)])
        before, _, _ = schedule(s, TODAY)
        self.assertEqual(before[D1][0][0]['id'], 'B')
        mutate(s, form(action='progress', id='A', actual='0.5', finished='yes'), TODAY)
        after, free, missing = schedule(s, TODAY)
        self.assertTrue(s['tasks'][0]['completed'])
        self.assertEqual(s['tasks'][0]['minutes'], 0)
        self.assertEqual(after[D0][0][0]['id'], 'B')
        self.assertEqual(sum(n for _, n in after[D0]), 60)
        self.assertEqual(spent_on(s, D0), 30)
        self.assertEqual(free[D0], 30)
        self.assertEqual(after[D1], [])
        self.assertEqual(missing, [])
        # Actual work remains deducted even if a task is deleted.
        mutate(s, form(action='delete', id='A'), TODAY)
        self.assertEqual(spent_on(s, D0), 30)

    def test_early_finish_without_next_task_leaves_free_time(self):
        """Verify early task completion leaves unused daily capacity available when no other tasks exist."""
        s = state([task(delta=0)])
        mutate(s, form(action='progress', id='a', actual='0.5', finished='yes'), TODAY)
        plan, free, _ = schedule(s, TODAY)
        self.assertEqual(plan[D0], [])
        self.assertEqual(free[D0], 90)

    def test_partial_work_does_not_create_capacity(self):
        """Verify partial progress reduces remaining task minutes without inflating daily capacity."""
        s = state([task()])
        mutate(s, form(action='progress', id='a', actual='0.5'), TODAY)
        plan, free, _ = schedule(s, TODAY)
        self.assertFalse(s['tasks'][0]['completed'])
        self.assertEqual(s['tasks'][0]['minutes'], 90)
        self.assertEqual(sum(n for _, n in plan[D0]), 90)
        self.assertEqual(free[D0], 0)

    def test_goal_stays_active_until_explicitly_completed(self):
        """Verify goal tasks stay active across progress logs until explicitly marked finished."""
        s = state([task(kind='goal')])
        mutate(s, form(action='progress', id='a', actual='0.5'), TODAY)
        self.assertFalse(s['tasks'][0]['completed'])
        mutate(s, form(action='progress', id='a', actual='0.5', finished='yes'), TODAY)
        self.assertTrue(s['tasks'][0]['completed'])
        with self.assertRaises(ValueError):
            mutate(s, form(action='progress', id='a', actual='0.5'), TODAY)

    def test_half_hour_and_invalid_numbers(self):
        """Verify hour-to-minute conversion enforces 0.5-hour increments, [0, 1000] bounds, and finite numbers."""
        for value in ['0.25', '0.75', 'nan', 'inf', '-inf', '-1', '1000.5', 'abc']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                minutes(value)
        self.assertEqual(minutes('0.5'), 30)
        self.assertEqual(minutes('0'), 0)
        self.assertEqual(minutes('1000'), 60000)
        s = state([])
        mutate(s, form(action='save', title='長期成長', kind='goal', important='yes'), TODAY)
        self.assertEqual(s['tasks'][0]['due'], '')
        with self.assertRaises(ValueError):
            mutate(s, form(action='save', title='missing ddl', kind='deadline', hours='1', important='yes'), TODAY)

    def test_dates_normalized_for_sorting(self):
        """Verify compact ISO date inputs (``YYYYMMDD``) are normalized to ``YYYY-MM-DD``."""
        s = state([])
        mutate(s, form(action='save', title='basic ISO', kind='deadline', hours='1', important='yes', due='20261106', start='20261105'), TODAY)
        self.assertEqual(s['tasks'][0]['due'], D1)
        self.assertEqual(s['tasks'][0]['start'], D0)
        self.assertEqual(sum(n for _, n in schedule(s, TODAY)[0][D0]), 60)

    def test_capacity_validation_and_spent_over_budget(self):
        """Verify daily capacity and cumulative logged work cannot exceed 24 hours (1440 minutes)."""
        s = state([task()])
        data = form(action='capacity', **{(TODAY + timedelta(days=i)).isoformat(): '1' for i in range(7)})
        data[D0] = ['24.5']
        with self.assertRaises(ValueError):
            mutate(s, data, TODAY)
        mutate(s, form(action='progress', id='a', actual='2.5'), TODAY)
        _, free, _ = schedule(s, TODAY)
        self.assertEqual(free[D0], 0)
        with self.assertRaises(ValueError):
            mutate(state([task()]), form(action='progress', id='a', actual='24.5'), TODAY)

    def test_allocation_invariants(self):
        """Verify conservation of capacity and total scheduled/missing task minutes across seed data."""
        s = seed(TODAY)
        plan, free, missing = schedule(s, TODAY)
        for day, rows in plan.items():
            used = sum(n for _, n in rows)
            self.assertEqual(used + free[day] + spent_on(s, day), s['capacity'][day])
            for t, n in rows:
                self.assertEqual(n % 30, 0)
                self.assertGreaterEqual(n, 30)
                self.assertLessEqual(day, t['due'])
                self.assertEqual(t['kind'], 'deadline')
        demand = sum(t['minutes'] for t in s['tasks'] if t['kind'] == 'deadline')
        self.assertEqual(sum(n for rows in plan.values() for _, n in rows) + sum(n for _, n, _ in missing), demand)
        self.assertEqual(schedule(empty_state(), TODAY)[2], [])

    def test_task_field_length_date_order_and_completed_lock_boundaries(self):
        """Boundary test: reject >100-char title, >60-char course, start > due, and editing completed tasks."""
        s = state([])
        with self.assertRaises(ValueError):
            mutate(s, form(action='save', title='x' * 101, kind='goal', important='yes'), TODAY)
        with self.assertRaises(ValueError):
            mutate(s, form(action='save', title='ok', course='c' * 61, kind='goal', important='yes'), TODAY)
        with self.assertRaises(ValueError):
            mutate(s, form(action='save', title='bad dates', kind='deadline', hours='1', important='yes', start=D1, due=D0), TODAY)

        mutate(s, form(action='save', title='Done Task', kind='deadline', hours='1', important='yes', due=D1), TODAY)
        tid = s['tasks'][0]['id']
        mutate(s, form(action='progress', id=tid, actual='1', finished='yes'), TODAY)
        with self.assertRaises(ValueError):
            mutate(s, form(action='save', id=tid, title='Reopen', kind='deadline', hours='1', important='yes', due=D1), TODAY)

    def test_goal_progress_clamps_ratio_at_one_when_exceeding_target(self):
        """Boundary test: ``goal_progress`` clamps completion ratio to 1.0 when invested hours exceed target."""
        s = state([])
        mutate(s, form(action='save', title='Read Book', kind='goal', important='yes', target_hours='1'), TODAY)
        goal = s['tasks'][0]
        self.assertEqual(goal_progress(s, goal), (0, 60, 0.0))
        mutate(s, form(action='progress', id=goal['id'], actual='1.5'), TODAY)
        invested, target, ratio = goal_progress(s, goal)
        self.assertEqual((invested, target), (90, 60))
        self.assertEqual(ratio, 1)


class StorageAndPageTests(unittest.TestCase):
    """Unit and boundary tests for JSON storage persistence, migration, corruption safety, and rendering."""

    def test_save_reload_and_restart_equivalence(self):
        """Verify saving and reloading state preserves all tasks, logs, and spent minutes across days."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'data.json'
            s = seed(TODAY)
            mutate(s, form(action='progress', id=s['tasks'][0]['id'], actual='0.5', finished='yes'), TODAY)
            save_state(path, s)
            restored, _ = load_state(path, TODAY + timedelta(days=1))
            self.assertEqual(restored, s)
            self.assertEqual(spent_on(restored, D0), 30)

    def test_legacy_migration_and_original_backup(self):
        """Verify v1 state rounds task/capacity minutes to 30-min steps and backs up original file as ``.v1.bak``."""
        old = {'tasks': [dict(id='a', title='old', course='test', due=D1, minutes=45, important=True)], 'capacity': {D0: 75}}
        original = json.dumps(old).encode()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'data.json'
            path.write_bytes(original)
            s, message = load_state(path, TODAY)
            self.assertEqual(s['tasks'][0]['minutes'], 60)
            self.assertEqual(s['capacity'][D0], 60)
            self.assertTrue(message)
            self.assertEqual(path.read_bytes(), original)
            save_state(path, s)
            self.assertEqual(path.with_suffix('.v1.bak').read_bytes(), original)
            self.assertEqual(json.loads(path.read_text())['version'], 2)

    def test_corrupt_json_and_schema_preserve_original(self):
        """Verify malformed JSON or invalid schema raises ``ValueError`` without modifying the file on disk."""
        for bad in [b'{broken', b'{"tasks": [], "capacity": {"bad-date": 5}}', b'[]']:
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'data.json'
                path.write_bytes(bad)
                with self.assertRaises(ValueError):
                    load_state(path, TODAY)
                self.assertEqual(path.read_bytes(), bad)

    def test_corrupt_file_starts_read_only_and_blocks_writes(self):
        """Verify HTTP server enters read-only mode (HTTP 503 on POST) when startup data is corrupted."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'data.json'
            path.write_bytes(b'{broken')
            with patch('android.runtime.main.HTTPServer', return_value=SimpleNamespace()):
                server = make_server(path)
            self.assertTrue(server.read_only)
            self.assertIn('原檔已保留', server.notice)
            handler = object.__new__(Handler)
            handler.server, handler.path = server, '/'
            with patch.object(handler, 'reply') as reply:
                handler.do_POST()
            self.assertEqual(reply.call_args.args[0], 503)
            self.assertEqual(path.read_bytes(), b'{broken')

    def test_failed_atomic_write_keeps_original(self):
        """Verify atomic write failure during ``Path.replace`` leaves existing state file untouched."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'data.json'
            save_state(path, seed(TODAY))
            before = path.read_bytes()
            with patch.object(Path, 'replace', side_effect=OSError('simulated write failure')):
                with self.assertRaises(OSError):
                    save_state(path, empty_state())
            self.assertEqual(path.read_bytes(), before)

    def test_migrate_rejects_duplicate_ids_and_overlapping_windows_or_blocks(self):
        """Boundary test: ``migrate()`` rejects duplicate task IDs, overlapping windows, and overlapping calendar blocks."""
        dup_tasks = [task('dup'), task('dup')]
        with self.assertRaises(ValueError):
            migrate(dict(version=2, tasks=dup_tasks, capacity={}))

        with self.assertRaises(ValueError):
            migrate(dict(version=2, tasks=[], capacity={}, availability={D0: [[540, 660], [600, 720]]}))

        overlap_cal = [
            dict(task_id='a', date=D0, start=540, end=630),
            dict(task_id='a', date=D0, start=600, end=690),
        ]
        with self.assertRaises(ValueError):
            migrate(dict(version=2, tasks=[task('a')], capacity={D0: 180}, calendar=overlap_cal))

    def test_page_explains_rules_and_escapes_input(self):
        """Verify HTML rendering escapes malicious script tags in task titles and exposes 0.5-hour step inputs."""
        s = state([task()])
        s['tasks'][0]['title'] = '<script>alert(1)</script>'
        with patch('android.runtime.main.today_hk', return_value=TODAY):
            page = render(s, query={'add': ['1']})
        self.assertNotIn('<script>', page)
        self.assertIn('&lt;script&gt;', page)
        self.assertIn('step="0.5"', page)
        self.assertNotIn('step="0.25"', page)
        self.assertIn('任務地圖', page)
        self.assertIn('action="/"', page)

    def test_pre_events_backup_created_once_on_legacy_calendar_model(self):
        """Edge case: ``save_state`` creates a one-time ``.pre-events.bak`` when upgrading pre-events-v4 files."""
        legacy_v2 = empty_state()
        legacy_v2['calendar_model'] = 'v3'
        original = json.dumps(legacy_v2).encode()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'data.json'
            path.write_bytes(original)
            updated = empty_state()
            updated['calendar_model'] = 'events-v4'
            save_state(path, updated)
            bak = path.with_suffix('.pre-events.bak')
            self.assertTrue(bak.exists())
            self.assertEqual(bak.read_bytes(), original)

    def test_migrate_rejects_malformed_override_date_keys(self):
        """Boundary test: ``migrate()`` rejects invalid ISO date keys inside event ``overrides``."""
        bad_event = dict(
            id='e1',
            title='Bad Override',
            date=D0,
            category='private',
            repeat='daily',
            until='',
            weekdays=[3],
            start=540,
            end=600,
            overrides={'not-a-date': {'cancelled': True}},
        )
        with self.assertRaises(ValueError):
            migrate(dict(version=2, tasks=[], capacity={}, events=[bad_event]))


if __name__ == '__main__':
    unittest.main()