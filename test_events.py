"""Unit tests for event recurrence, privacy rules, overrides, and timetable drag-and-drop.

Covers fixed vs. private event availability filtering, daily/weekly/monthly/workday/holiday
recurrence boundaries, overnight splitting across midnight, urgent private-time borrowing
thresholds, single-occurrence rescheduling/cancellation, and interactive block dragging.
"""
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from android.runtime.main import event_bubble, render, render_calendar
from events import cancel_occurrence, move_occurrence, occurrences, save_event
from storage import empty_state, load_state, save_state
from test_planner import D0, D1, TODAY, form, state, task
from timetable import available_cells, candidate, cells, move_block, refresh


def event(ident='e', day=D0, start=540, end=600, category='fixed', repeat='none', weekdays=None, until=''):
    """Construct a valid event dictionary for test fixtures.

    Args:
        ident (str, optional): Unique event identifier. Defaults to ``'e'``.
        day (str, optional): Start date in ISO format. Defaults to ``D0``.
        start (int, optional): Start time in minutes from midnight. Defaults to ``540``.
        end (int, optional): End time in minutes from midnight. Defaults to ``600``.
        category (str, optional): Event category (``'fixed'`` or ``'private'``).
            Defaults to ``'fixed'``.
        repeat (str, optional): Recurrence rule. Defaults to ``'none'``.
        weekdays (list[int] | None, optional): Weekday indices for weekly rules.
            Defaults to the weekday of ``day``.
        until (str, optional): Inclusive recurrence end date in ISO format.
            Defaults to ``''``.

    Returns:
        dict: Normalized event dictionary matching the storage schema.
    """
    return dict(
        id=ident,
        title=ident,
        category=category,
        date=day,
        start=start,
        end=end,
        repeat=repeat,
        weekdays=weekdays or [date.fromisoformat(day).weekday()],
        until=until,
        overrides={},
    )


def free_state(tasks=None):
    """Create a test state configured with the ``'free'`` 24-hour time model.

    Args:
        tasks (list[dict] | None, optional): Initial task list. Defaults to ``None``.

    Returns:
        dict: State dictionary with ``time_model == 'free'``.
    """
    s = state(tasks or [])
    s['time_model'] = 'free'
    return s


class RecurrenceAndPrivacyTests(unittest.TestCase):
    """Tests for event expansion, recurrence edge cases, privacy borrowing, and overrides."""

    def test_unassigned_work_hours_are_free_not_assumed_busy(self):
        """Verify that ``'free'`` mode exposes all 48 half-hour slots per day across 7 days."""
        s = free_state()
        free = available_cells(s, TODAY)
        self.assertIn((D0, 8 * 60), free)
        self.assertIn((D0, 15 * 60 + 30), free)
        self.assertIn((D0, 23 * 60), free)
        self.assertEqual(len(free), 7 * 48)

    def test_fixed_and_private_are_removed_before_scheduling(self):
        """Verify that both fixed and private event blocks are excluded from default free cells."""
        s = free_state()
        s['events'] = [event(start=540, end=660), event('p', start=660, end=720, category='private')]
        free = available_cells(s, TODAY)
        # Slots before 09:00 (540) and from 12:00 (720) remain free; 09:00–12:00 are blocked
        self.assertIn((D0, 480), free)
        self.assertNotIn((D0, 540), free)
        self.assertNotIn((D0, 690), free)
        self.assertIn((D0, 720), free)

    def test_daily_and_until_are_inclusive(self):
        """Verify that daily recurrence includes both the start date and the ``until`` date."""
        s = free_state()
        s['events'] = [event(repeat='daily', until=D1)]
        rows = occurrences(s, TODAY, TODAY + timedelta(days=6))
        self.assertEqual([b['date'] for b in rows], [D0, D1])

    def test_weekly_multiple_days(self):
        """Verify that weekly recurrence expands across multiple selected weekdays."""
        s = free_state()
        # 2026-11-05 is Thursday (3); [3, 5] expands to Thu, Sat, next Thu
        s['events'] = [event(repeat='weekly', weekdays=[3, 5])]
        rows = occurrences(s, TODAY, TODAY + timedelta(days=8))
        self.assertEqual([date.fromisoformat(b['date']).weekday() for b in rows], [3, 5, 3])

    def test_monthly_31_skips_short_month_and_crosses_year(self):
        """Verify that monthly events on the 31st skip 30/28-day months and cross year boundaries."""
        s = free_state()
        s['events'] = [event(day='2026-12-31', repeat='monthly')]
        rows = occurrences(s, date(2026, 12, 31), date(2027, 3, 31))
        # Feb 2027 has no 31st and is skipped cleanly
        self.assertEqual([b['date'] for b in rows], ['2026-12-31', '2027-01-31', '2027-03-31'])

    def test_overnight_is_split_and_previous_day_tail_visible(self):
        """Verify that an overnight event splits at 24:00 (1440) and its tail renders next day."""
        s = free_state()
        # 22:00–06:00 (1320..1800) splits at midnight into D0 [1320, 1440] and D1 [0, 360]
        s['events'] = [event(start=1320, end=1800)]
        rows = occurrences(s, TODAY, TODAY + timedelta(days=1))
        self.assertEqual([(b['date'], b['start'], b['end']) for b in rows], [(D0, 1320, 1440), (D1, 0, 360)])
        # Querying D1 alone still surfaces the early-morning tail carried over from D0
        tail = occurrences(s, TODAY + timedelta(days=1), TODAY + timedelta(days=1))
        self.assertEqual([(b['start'], b['end']) for b in tail], [(0, 360)])

    def test_private_time_renders_in_local_android_calendar(self):
        s = free_state()
        s['events'] = [event('Private time', category='private')]
        html = render_calendar(s, TODAY, [])
        self.assertIn('Private time', html)
        self.assertIn('data-draggable="true"', html)

    def test_moved_private_time_stays_reserved_after_original_date(self):
        s = free_state()
        s['events'] = [event(category='private')]
        moved_day = (TODAY + timedelta(days=5)).isoformat()
        move_occurrence(s, form(id='e', occurrence_date=D0,
                                new_date=moved_day, new_start='11:00'), TODAY)
        later = TODAY + timedelta(days=3)
        rows = occurrences(s, later, later + timedelta(days=6))
        self.assertEqual([(b['date'], b['start'], b['end']) for b in rows],
                         [(moved_day, 660, 720)])
        self.assertNotIn((moved_day, 660), available_cells(s, later))

    def test_form_accepts_overnight_rejects_quarter_hour_and_same_times(self):
        """Verify form validation accepts overnight intervals but rejects 15-min steps or zero duration."""
        s = free_state()
        data = form(action='save_event', title='夜班', category='fixed', date=D0, event_start='22:00', event_end='06:00', repeat='daily')
        save_event(s, data)
        self.assertEqual(s['events'][0]['end'], 1800)
        for bad in ['22:15', '22:00']:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                save_event(free_state(), dict(data, event_end=[bad]))

    def test_private_borrow_requires_opt_in_and_urgent_deadline(self):
        """Verify private slots can only be borrowed when opted in AND task due <= today + 3 days."""
        s = state([task(delta=0, amount=60)])
        s['availability'] = {D0: [[540, 600]]}
        s['capacity'] = {D0: 60}
        s['events'] = [event(category='private')]
        # Disabled by default -> cannot borrow private time
        self.assertEqual(candidate(s, TODAY)[0], [])
        # Enabled + due within 3 days -> borrowing succeeds
        s['borrow_private'] = True
        self.assertEqual(len(cells(candidate(s, TODAY)[0])), 2)
        # Due at day +4 -> beyond 3-day urgency cutoff, borrowing stops
        s['tasks'][0]['due'] = (TODAY + timedelta(days=4)).isoformat()
        self.assertEqual(candidate(s, TODAY)[0], [])

    def test_fixed_never_borrowed_even_under_private_override(self):
        """Verify that fixed appointments are strictly protected even when ``borrow_private`` is True."""
        s = state([task(delta=0, amount=60)])
        s['availability'] = {D0: [[540, 600]]}
        s['capacity'] = {D0: 60}
        s['events'] = [event(category='private'), event('fixed', start=540, end=570)]
        s['borrow_private'] = True
        plan, missing = candidate(s, TODAY)
        # Only the second half-hour (570..600) can be borrowed; 540..570 remains locked by fixed event
        self.assertEqual(set(cells(plan)), {(D0, 570)})
        self.assertEqual(missing[0][1], 30)

    def test_normal_free_time_used_before_private_time(self):
        """Verify that unblocked free slots are consumed before borrowing private time."""
        s = state([task(delta=0, amount=60)])
        s['availability'] = {D0: [[540, 660]]}
        s['capacity'] = {D0: 120}
        s['events'] = [event(category='private')]
        s['borrow_private'] = True
        # Scheduler picks 10:00–11:00 (600, 630) rather than touching the 09:00–10:00 private event
        self.assertEqual(set(cells(candidate(s, TODAY)[0])), {(D0, 600), (D0, 630)})

    def test_moving_one_weekly_occurrence_keeps_other_weeks(self):
        """Verify that rescheduling a single weekly occurrence leaves subsequent weeks intact."""
        s = free_state()
        s['events'] = [event(repeat='weekly', category='private')]
        move_occurrence(s, form(id='e', occurrence_date=D0, new_date=D1, new_start='11:00'), TODAY)
        rows = occurrences(s, TODAY, TODAY + timedelta(days=8))
        self.assertEqual([(b['date'], b['start']) for b in rows], [(D1, 660), ((TODAY + timedelta(days=7)).isoformat(), 540)])

    def test_recurring_override_persists_with_private_policy(self):
        """Verify that single-instance overrides and ``borrow_private`` survive JSON save/load."""
        s = free_state()
        s['events'] = [event(repeat='daily', category='private')]
        s['borrow_private'] = True
        move_occurrence(s, form(id='e', occurrence_date=D0, new_date=D1, new_start='11:00'), TODAY)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'data.json'
            save_state(path, s)
            restored, _ = load_state(path, TODAY)
        self.assertEqual(restored, s)

    def test_full_day_boundary_and_until_before_start_rejected(self):
        """Boundary test: accept 00:00–24:00 (1440 min) and reject ``until`` earlier than ``date``."""
        s = free_state()
        save_event(
            s,
            form(action='save_event', title='全天研討會', category='fixed', date=D0, event_start='00:00', event_end='24:00', repeat='none'),
        )
        self.assertEqual((s['events'][0]['start'], s['events'][0]['end']), (0, 1440))
        with self.assertRaises(ValueError):
            save_event(
                free_state(),
                form(action='save_event', title='倒置日期', category='private', date=D1, until=D0, event_start='09:00', event_end='10:00', repeat='daily'),
            )

    def test_workdays_and_holidays_recurrence_respects_hk_gazette(self):
        """Edge case: ``workdays`` skips HK statutory holidays (2026-01-01) while ``holidays`` matches them."""
        s = free_state()
        s['events'] = [
            event('w', day='2026-01-01', repeat='workdays', until='2026-01-04'),
            event('h', day='2026-01-01', repeat='holidays', until='2026-01-04'),
        ]
        rows = occurrences(s, date(2026, 1, 1), date(2026, 1, 4))
        workday_dates = [b['date'] for b in rows if b['event_id'] == 'w']
        holiday_dates = [b['date'] for b in rows if b['event_id'] == 'h']
        # 2026-01-01 (Thu) is New Year's Day; 2026-01-02 (Fri) is workday; Jan 3 (Sat) & Jan 4 (Sun) are non-workdays
        self.assertEqual(workday_dates, ['2026-01-02'])
        self.assertEqual(holiday_dates, ['2026-01-01', '2026-01-03', '2026-01-04'])

    def test_cancel_overnight_occurrence_removes_both_halves_and_prevents_double_cancel(self):
        """Edge case: cancelling an overnight occurrence removes both day segments and blocks duplicate cancel."""
        s = free_state()
        s['availability'][D0] = []
        s['events'] = [event('night', day=D0, start=1380, end=1500, category='private', repeat='daily')]
        cancel_occurrence(s, form(id='night', occurrence_date=D0))
        rows = occurrences(s, TODAY, TODAY + timedelta(days=1))
        # D0's occurrence (and its D1 00:00–01:00 tail) must be gone; only D1's 23:00–24:00 remains
        self.assertEqual([(b['date'], b['start'], b['end']) for b in rows], [(D1, 1380, 1440)])
        with self.assertRaises(ValueError):
            cancel_occurrence(s, form(id='night', occurrence_date=D0))

    def test_overnight_fixed_event_blocks_next_morning_task_scheduling(self):
        """Cross-module edge case: an overnight fixed event on D0 blocks early-morning task slots on D1."""
        s = state([task('morning', delta=1, amount=60)])
        s['availability'] = {D0: [], D1: [[0, 600]]}
        s['capacity'] = {D0: 0, D1: 600}
        # 22:00–06:00 fixed event on D0 occupies D1 00:00–06:00 (0..360), pushing task to 06:00–07:00
        s['events'] = [event('night_fixed', day=D0, start=1320, end=1800, category='fixed', repeat='none')]
        plan, _ = candidate(s, TODAY)
        self.assertEqual(set(cells(plan)), {(D1, 360), (D1, 390)})

    def test_delete_event_removes_series_and_rejects_missing_id(self):
        """Edge case: ``save_event`` with ``delete_event`` removes the event and raises on unknown ID."""
        s = free_state()
        save_event(s, form(action='save_event', title='Temp', category='private', date=D0, event_start='09:00', event_end='10:00', repeat='daily'))
        eid = s['events'][0]['id']
        save_event(s, form(action='delete_event', id=eid))
        self.assertEqual(s['events'], [])
        with self.assertRaises(ValueError):
            save_event(s, form(action='delete_event', id='nonexistent'))


class DragAndBubbleTests(unittest.TestCase):
    """Tests for interactive timetable block dragging, pinning, and UI rendering."""

    def test_delaying_one_hour_task_leaves_rest_gap_and_other_work_unchanged(self):
        """Verify dragging one block forward leaves an open gap and preserves adjacent tasks."""
        s = state([task('prior', delta=0, amount=60), task('work', delta=0, amount=60)])
        s['availability'] = {D0: [[540, 720]]}
        s['capacity'] = {D0: 180}
        s['calendar'] = [dict(task_id='prior', date=D0, start=540, end=600), dict(task_id='work', date=D0, start=600, end=660)]
        before = deepcopy(s['calendar'][0])
        move_block(s, form(id='work', source_date=D0, source_start='10:00', source_end='11:00', new_date=D0, new_start='11:00'), TODAY)
        # Earlier task stays at 09:00–10:00, 10:00–11:00 becomes open gap, dragged task sits at 11:00–12:00
        self.assertEqual(s['calendar'][0], before)
        self.assertFalse(any((D0, m) in cells(s['calendar']) for m in (600, 630)))
        self.assertEqual({cell for cell, ident in cells(s['calendar']).items() if ident == 'work'}, {(D0, 660), (D0, 690)})
        self.assertEqual(s['tasks'][1]['minutes'], 60)

    def example(self):
        """Build a standard two-task refreshed state fixture for drag tests.

        Returns:
            dict: Refreshed state with task ``'A'`` (2h due D0) and task ``'B'`` (1h due D1).
        """
        s = state([task('A', delta=0, amount=120), task('B', delta=1, amount=60)])
        s['availability'] = {D0: [[540, 840]]}
        s['capacity'] = {D0: 300}
        refresh(s, TODAY)
        return s

    def test_manual_drag_retained_on_next_replan(self):
        """Verify manually dragged task blocks are pinned and survive subsequent ``refresh()`` calls."""
        s = self.example()
        data = form(id='B', source_date=D0, source_start='11:00', source_end='12:00', new_date=D0, new_start='13:00')
        move_block(s, data, TODAY)
        s['tasks'].append(task('C', delta=0, amount=60))
        refresh(s, TODAY)
        # Pinned B stays at 13:00 (780); newly added C fills the freed 11:00 (660) gap
        self.assertEqual(cells(s['calendar'])[(D0, 780)], 'B')
        self.assertEqual(cells(s['calendar'])[(D0, 660)], 'C')

    def test_drag_rejects_task_fixed_private_deadline_and_stale_conflicts(self):
        """Verify dragging rejects collisions with tasks, fixed/private events, due bounds, and stale blocks."""
        # Reject collisions against existing task (09:00), fixed event (12:00), and private event (12:30)
        for bad in ['09:00', '12:00', '12:30']:
            s = self.example()
            s['events'] = [event(start=720, end=750), event('p', start=750, end=780, category='private')]
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                move_block(s, form(id='B', source_date=D0, source_start='11:00', source_end='12:00', new_date=D0, new_start=bad), TODAY)
        s = self.example()
        # Reject dragging task A past its D0 due date onto D1
        with self.assertRaises(ValueError):
            move_block(s, form(id='A', source_date=D0, source_start='09:00', source_end='11:00', new_date=D1, new_start='09:00'), TODAY)
        # Reject dragging with stale source timestamps (10:30–11:30 instead of 11:00–12:00)
        with self.assertRaises(ValueError):
            move_block(s, form(id='B', source_date=D0, source_start='10:30', source_end='11:30', new_date=D0, new_start='13:00'), TODAY)

    def test_drag_rejects_crossing_midnight_boundary(self):
        """Boundary test: dragging a 1-hour block to 23:30 (ending at 24:30) must raise ``ValueError``."""
        s = self.example()
        s['time_model'] = 'free'
        refresh(s, TODAY)
        with self.assertRaises(ValueError):
            move_block(s, form(id='B', source_date=D0, source_start='11:00', source_end='12:00', new_date=D0, new_start='23:30'), TODAY)

    def test_private_override_disabling_removes_borrowed_pin(self):
        """Verify disabling ``borrow_private`` automatically prunes pins that relied on private time."""
        s = self.example()
        s['tasks'][1]['due'] = D0
        s['events'] = [event(category='private', start=780, end=840)]
        s['borrow_private'] = True
        move_block(s, form(id='B', source_date=D0, source_start='11:00', source_end='12:00', new_date=D0, new_start='13:00'), TODAY)
        # Turning off borrow_private must invalidate and clear the pin inside the private block
        s['borrow_private'] = False
        refresh(s, TODAY)
        self.assertNotIn((D0, 780), cells(s['calendar']))
        self.assertEqual(s['pins'], [])

    def test_full_day_grid_events_tab_and_bubble_markup(self):
        """Verify HTML rendering of the 00:00–24:00 timetable grid, draggable blocks, and event panel."""
        s = self.example()
        s['events'] = [event()]
        with patch('android.runtime.main.today_hk', return_value=TODAY):
            schedule = render(s, query={'tab': ['schedule']})
            detail = render(s, query={'task': ['A']})
            panel = render(s, query={'tab': ['events']})
        self.assertIn('00:00', schedule)
        self.assertIn('24:00', schedule)
        self.assertIn('data-draggable="true"', schedule)
        self.assertIn('anchor-bubble', detail)
        self.assertNotIn('drawer-shade', detail)
        self.assertIn('固定事項', panel)
        self.assertIn('允許緊急 DDL', panel)
        self.assertIn('app.js', schedule)


class ValidationEventsIntegrationTests(unittest.TestCase):
    """Cross-module integration tests linking ``validation`` and ``events``."""

    def test_normalized_overnight_event_and_date_boundary_pipeline(self):
        """Verify normalize_fields, parse_date, save_event, and overnight expansion together."""
        from storage import empty_state
        from validation import normalize_fields
        from events import save_event, occurrences

        state = empty_state()

        # 1. Invalid calendar date is caught cleanly by parse_date inside save_event
        bad_date_payload = normalize_fields({
            'title': 'Late Lab',
            'category': 'fixed',
            'date': '2026-02-30',
            'event_start': '23:00',
            'event_end': '01:00',
            'repeat': 'none',
        })
        with self.assertRaisesRegex(ValueError, '日期無效'):
            save_event(state, bad_date_payload)

        # 2. Inverted until boundary (until < date) is rejected after valid date parsing
        inverted_until_payload = normalize_fields({
            'title': 'Late Lab',
            'category': 'fixed',
            'date': '2026-11-15',
            'until': '2026-11-14',
            'event_start': '23:00',
            'event_end': '01:00',
            'repeat': 'daily',
        })
        with self.assertRaisesRegex(ValueError, '重複結束日期不能早於開始日期'):
            save_event(state, inverted_until_payload)

        # 3. Valid normalized overnight event saves and expands across midnight into two segments
        valid_payload = normalize_fields({
            'title': 'Late Lab',
            'category': 'fixed',
            'date': '2026-11-14',
            'until': '2026-11-15',
            'event_start': '23:00',
            'event_end': '01:00',
            'repeat': 'none',
        })
        save_event(state, valid_payload)
        blocks = occurrences(state, date(2026, 11, 14), date(2026, 11, 15))
        self.assertEqual([(b['date'], b['start'], b['end']) for b in blocks], [
            ('2026-11-14', 1380, 1440),
            ('2026-11-15', 0, 60),
        ])


if __name__ == '__main__':
    unittest.main()