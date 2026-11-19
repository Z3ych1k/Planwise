"""Regressions and boundary checks: locked fixed events and non-blocking move suggestions.

Verifies single-occurrence cancellation across overnight splits, immutability of fixed
appointments under direct POST requests, preservation of cancelled dates across series
edits, 7-day horizon boundaries for private occurrence moves, and non-blocking HTTP
workflows while a schedule move proposal is pending.
"""
from copy import deepcopy
from datetime import timedelta
from io import BytesIO
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from android.runtime.main import Handler, TOKEN, event_bubble, render
from events import cancel_occurrence, move_occurrence, occurrences, save_event
from storage import load_state, save_state
from test_events import event
from test_planner import D0, D1, TODAY, form, task
from test_timetable import early_finish, example
from timetable import cells, decide, refresh


def request(state, path, **fields):
    """Simulate an authenticated JSON POST request against ``Handler.do_POST``.

    Args:
        state (dict): Mutable in-memory application state attached to the mock server.
        path (pathlib.Path): Temporary filesystem path for persisting state changes.
        **fields: Form fields to encode into the POST request body.

    Returns:
        tuple[dict, tuple[int, dict]]: A 2-tuple ``(updated_state, (status_code, json_body))``.
    """
    payload = urlencode(dict(token=TOKEN, tab='schedule', **fields)).encode()
    handler = Handler.__new__(Handler)
    handler.path = '/'
    handler.headers = {'Content-Length': str(len(payload)), 'Accept': 'application/json'}
    handler.rfile = BytesIO(payload)
    handler.server = SimpleNamespace(state=state, data_path=path, notice='', demo=False, read_only=False)
    result = []
    handler.reply = lambda code, body, *args, **kwargs: result.append((code, json.loads(body)))
    with patch('android.runtime.main.today_hk', return_value=TODAY), patch('android.runtime.main.current_floor', return_value=0):
        handler.do_POST()
    return handler.server.state, result[0]


class FixedEventTests(unittest.TestCase):
    """Tests for fixed-event immutability, single-occurrence cancellation, and override boundaries."""

    def test_cancel_one_daily_overnight_occurrence_and_persist(self):
        """Verify cancelling one overnight daily occurrence removes both day segments and persists."""
        s = example()
        # Daily overnight event 22:00–06:00 (1320–1800) starting on D0
        s['events'] = [event(start=1320, end=1800, repeat='daily')]
        cancel_occurrence(s, form(id='e', occurrence_date=D0))
        rows = occurrences(s, TODAY, TODAY + timedelta(days=2))
        # Both D0's late-night half and D1's early-morning tail from D0 must be suppressed
        self.assertFalse(any(r['occurrence_date'] == D0 for r in rows))
        self.assertEqual([(r['date'], r['start']) for r in rows], [(D1, 1320), ((TODAY + timedelta(days=2)).isoformat(), 0), ((TODAY + timedelta(days=2)).isoformat(), 1320)])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'data.json'
            save_state(path, s)
            restored, _ = load_state(path, TODAY)
        self.assertEqual(occurrences(restored, TODAY, TODAY + timedelta(days=2)), rows)

    def test_fixed_event_cannot_move_even_with_direct_post(self):
        """Verify fixed events reject ``move_occurrence`` and render with ``data-draggable="false"``."""
        s = example()
        s['events'] = [event(repeat='daily')]
        before = deepcopy(s)
        with self.assertRaisesRegex(ValueError, '固定事項不能移動'):
            move_occurrence(s, form(id='e', occurrence_date=D0, new_date=D1, new_start='11:00'), TODAY)
        self.assertEqual(s, before)
        # Bubble popup and timetable grid must disable drag-and-drop for fixed events
        html = event_bubble(s, TODAY, 'e', 'schedule', {'occurrence_date': [D1]})
        self.assertIn('cancel_occurrence', html)
        self.assertIn('value="' + D1 + '"', html)
        self.assertNotIn('name="new_start"', html)
        with patch('android.runtime.main.today_hk', return_value=TODAY):
            html = render(s, query={'tab': ['schedule']})
        self.assertIn('data-end="600" data-draggable="false"', html)

    def test_invalid_and_repeated_cancellation_rejected(self):
        """Verify cancelling a non-matching occurrence date or an already-cancelled date raises ``ValueError``."""
        s = example()
        s['events'] = [event(repeat='weekly')]
        # D1 is not the weekly weekday, so cancelling D1 must fail without mutating overrides
        with self.assertRaises(ValueError):
            cancel_occurrence(s, form(id='e', occurrence_date=D1))
        self.assertEqual(s['events'][0]['overrides'], {})
        cancel_occurrence(s, form(id='e', occurrence_date=D0))
        with self.assertRaises(ValueError):
            cancel_occurrence(s, form(id='e', occurrence_date=D0))

    def test_series_edit_keeps_cancelled_dates_but_clears_moved_overrides(self):
        """Edge case: editing an event series preserves cancelled dates while resetting single-day time moves."""
        s = example()
        s['events'] = [event(repeat='daily', category='private')]
        move_occurrence(s, form(id='e', occurrence_date=D0, new_date=D0, new_start='14:00'), TODAY)
        cancel_occurrence(s, form(id='e', occurrence_date=D1))
        # Editing series resets D0 back to 10:00 (600) while keeping D1 cancelled
        save_event(s, form(action='save_event', id='e', title='New title', category='private', date=D0, event_start='10:00', event_end='11:00', repeat='daily'))
        expanded = occurrences(s, TODAY, TODAY + timedelta(days=2))
        self.assertFalse(any(r['date'] == D1 for r in expanded))
        self.assertEqual([(r['date'], r['start']) for r in expanded], [(D0, 600), ((TODAY + timedelta(days=2)).isoformat(), 600)])

    def test_move_occurrence_enforces_seven_day_window_and_2400_boundary(self):
        """Boundary test: private occurrence moves must stay within ``[today, today + 6]`` and start before ``24:00``."""
        s = example()
        s['events'] = [event(repeat='daily', category='private')]
        day_7 = (TODAY + timedelta(days=7)).isoformat()
        day_6 = (TODAY + timedelta(days=6)).isoformat()
        # Day +7 (outside 7-day window) and 24:00 start time must both be rejected
        with self.assertRaises(ValueError):
            move_occurrence(s, form(id='e', occurrence_date=D0, new_date=day_7, new_start='10:00'), TODAY)
        with self.assertRaises(ValueError):
            move_occurrence(s, form(id='e', occurrence_date=D0, new_date=day_6, new_start='24:00'), TODAY)
        # Day 6 (inclusive upper boundary) at 23:30 must succeed
        move_occurrence(s, form(id='e', occurrence_date=D0, new_date=day_6, new_start='23:30'), TODAY)
        self.assertEqual(s['events'][0]['overrides'][D0]['date'], day_6)


class NonblockingSuggestionTests(unittest.TestCase):
    """Tests ensuring pending move proposals never block concurrent logging, edits, or drags."""

    def pending(self):
        """Create an example state with an active move proposal and a long-term goal task.

        Returns:
            dict: State dictionary containing a pending ``proposal``.
        """
        s = example()
        early_finish(s)
        s['tasks'].append(task('goal', kind='goal'))
        return s

    def test_repeated_logs_accepted_while_suggestion_pending(self):
        """Verify logging goal effort while a proposal is pending updates the proposal ID without moving existing blocks."""
        s = self.pending()
        old = deepcopy(s['calendar'])
        revision = s['proposal']['id']
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'data.json'
            save_state(path, s)
            for start in ('18:30', '19:00'):
                s, (code, reply) = request(s, path, action='progress', id='goal', actual='0.5', session_start=start)
                self.assertEqual(code, 200, reply)
                self.assertEqual(s['calendar'], old)
                self.assertNotEqual(s['proposal']['id'], revision)
            restored, _ = load_state(path, TODAY)
        self.assertEqual(sum(r['minutes'] for r in s['work_log'] if r['task_id'] == 'goal'), 60)
        self.assertEqual(s, restored)
        # Outdated proposal revision ID must no longer be confirmable
        with self.assertRaises(ValueError):
            decide(s, 'confirm_move', revision, TODAY)

    def test_new_task_and_task_edit_do_not_move_existing_schedule(self):
        """Verify creating or editing tasks keeps already-accepted calendar blocks in place."""
        s = self.pending()
        old = deepcopy(s['calendar'])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'data.json'
            s, (code, reply) = request(s, path, action='save', id='', title='C', kind='deadline', due=D0, hours='0.5', important='yes')
            self.assertEqual(code, 200, reply)
            self.assertTrue(all(b in s['calendar'] for b in old))
            s, (code, reply) = request(s, path, action='save', id='B', title='Renamed', kind='deadline', due=D1, hours='1', important='no')
            self.assertEqual(code, 200, reply)
            self.assertTrue(all(b in s['calendar'] for b in old))

    def test_duplicate_actual_work_still_rejected_during_suggestion(self):
        """Verify overlapping work-log timestamps return HTTP 400 without corrupting the pending proposal."""
        s = self.pending()
        revision = s['proposal']['id']
        with tempfile.TemporaryDirectory() as folder:
            s, (code, reply) = request(s, Path(folder) / 'data.json', action='progress', id='B', actual='0.5', session_start='18:00')
        # This logging conflicts with A's existing actual work and is correctly rejected.
        self.assertEqual(code, 400)
        self.assertEqual(s['proposal']['id'], revision)

    def test_task_progress_reduces_original_block_before_optional_move(self):
        """Verify partial work logged against a deadline task shrinks its existing calendar block immediately."""
        s = self.pending()
        revision = s['proposal']['id']
        with tempfile.TemporaryDirectory() as folder:
            s, (code, reply) = request(s, Path(folder) / 'data.json', action='progress', id='B', actual='0.5', session_start='18:30')
        self.assertEqual(code, 200, reply)
        # Task B shrinks from 60 min (1080–1140) to 30 min (1080–1110) in place
        self.assertEqual(s['calendar'], [dict(task_id='B', date=D1, start=1080, end=1110)])
        self.assertEqual(next(t for t in s['tasks'] if t['id'] == 'B')['minutes'], 30)
        self.assertNotEqual(s['proposal']['id'], revision)

    def test_cancel_event_pending_keeps_other_tasks_and_releases_only_one_date(self):
        """Verify cancelling a single event occurrence during a pending proposal leaves current task blocks intact."""
        s = self.pending()
        s['events'] = [event(repeat='daily', start=600, end=660)]
        old = deepcopy(s['calendar'])
        with tempfile.TemporaryDirectory() as folder:
            s, (code, reply) = request(s, Path(folder) / 'data.json', action='cancel_occurrence', id='e', occurrence_date=D0)
        self.assertEqual(code, 200, reply)
        self.assertEqual(s['calendar'], old)
        self.assertFalse(any(r['date'] == D0 for r in occurrences(s, TODAY, TODAY + timedelta(days=1))))
        self.assertTrue(any(r['date'] == D1 for r in occurrences(s, TODAY, TODAY + timedelta(days=1))))

    def test_drag_original_works_during_suggestion(self):
        """Verify manual drag-and-drop rescheduling succeeds even while a move proposal is pending."""
        s = self.pending()
        with tempfile.TemporaryDirectory() as folder:
            s, (code, reply) = request(s, Path(folder) / 'data.json', action='move_block', id='B', source_date=D1, source_start='18:00', source_end='19:00', new_date=D0, new_start='19:00')
        self.assertEqual(code, 200, reply)
        self.assertEqual(cells(s['calendar']), {(D0, 1140): 'B', (D0, 1170): 'B'})

    def test_decide_rejects_stale_date_and_unknown_action_without_mutating_calendar(self):
        """Boundary test: ``decide()`` rejects proposals from a different date or invalid decision strings."""
        s = self.pending()
        before = deepcopy(s['calendar'])
        rev = s['proposal']['id']
        with self.assertRaises(ValueError):
            decide(s, 'confirm_move', rev, TODAY + timedelta(days=1))
        with self.assertRaises(ValueError):
            decide(s, 'invalid_choice', rev, TODAY)
        self.assertEqual(s['calendar'], before)


if __name__ == '__main__':
    unittest.main()