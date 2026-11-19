"""Unit and boundary tests for 30-minute timetable slots, windows, and move approvals.

Covers multi-window task splitting, move-proposal diffing and explicit confirmation,
stale proposal expiration across day boundaries, custom availability window validation,
``not_before`` current-time cutoffs, midnight boundaries, and legacy work-log slot fallback.
"""
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from android.runtime.main import render
from planner import mutate
from storage import load_state, save_state
from test_planner import D0, D1, TODAY, form, state, task
from timetable import (
    available_cells,
    blocks_from_cells,
    candidate,
    cells,
    clock,
    decide,
    initialize,
    occupied,
    preview_parts,
    record_clock,
    refresh,
    stamp,
    update_windows,
)


def example():
    """Build an initialized two-task timetable state fixture for move-proposal tests.

    Returns:
        dict: State with task ``'A'`` (2h due ``D0``) and task ``'B'`` (1h due ``D1``),
        configured with evening availability windows on ``D0`` and ``D1``.
    """
    s = state([task('A', delta=0), task('B', delta=1, amount=60)])
    s['availability'] = {D0: [[1080, 1200]], D1: [[1080, 1140]]}
    s['capacity'] = {D0: 120, D1: 60}
    initialize(s, TODAY)
    return s


def early_finish(s):
    """Log early completion of task ``'A'`` at 18:00–18:30 and trigger a move proposal.

    Args:
        s (dict): Mutable state fixture returned by ``example()``.
    """
    data = form(action='progress', id='A', actual='0.5', finished='yes', session_start='18:00')
    begin, end = record_clock(s, data, TODAY)
    mutate(s, data, TODAY)
    s['work_log'][-1].update(start=begin, end=end)
    refresh(s, TODAY, propose=True)


class ClockAndApprovalTests(unittest.TestCase):
    """Tests for half-hour clock parsing, availability windows, and move-proposal workflows."""

    def test_split_across_two_windows_and_respect_actual(self):
        """Verify tasks split cleanly across disjoint daily windows and skip already-logged slots."""
        s = state([task(amount=180)])
        s['availability'] = {D0: [[540, 600], [900, 960]], D1: [[600, 660]]}
        plan, missing = candidate(s, TODAY)
        self.assertEqual([(b['date'], b['start'], b['end']) for b in plan], [(D0, 540, 600), (D0, 900, 960), (D1, 600, 660)])
        self.assertEqual(missing, [])
        # Mark 09:00–09:30 as already logged; candidate() must skip that slot
        s['work_log'] = [dict(task_id='other', title='other', date=D0, minutes=30, start=540, end=570, finished=False)]
        plan, _ = candidate(s, TODAY)
        self.assertNotIn((D0, 540), cells(plan))

    def test_early_finish_keeps_origin_until_confirmation(self):
        """Verify early task completion stages a move proposal without altering accepted blocks until confirmed."""
        s = example()
        early_finish(s)
        self.assertIsNotNone(s['proposal'])
        # Active calendar stays at D1 until the user explicitly confirms the move
        self.assertEqual(s['calendar'], [dict(task_id='B', date=D1, start=1080, end=1140)])
        solid, old, new = preview_parts(s)
        self.assertEqual(solid, [])
        self.assertEqual(old, s['calendar'])
        self.assertEqual(new, [dict(task_id='B', date=D0, start=1110, end=1170)])
        self.assertEqual(occupied(s, D0), {1080})

    def test_confirm_changes_destination_to_solid(self):
        """Verify confirming a pending proposal applies the proposed schedule and clears ``proposal``."""
        s = example()
        early_finish(s)
        expected = deepcopy(s['proposal']['after'])
        decide(s, 'confirm_move', s['proposal']['id'], TODAY)
        self.assertEqual(s['calendar'], expected)
        self.assertEqual(preview_parts(s), (expected, [], []))
        self.assertIsNone(s['proposal'])

    def test_decline_retains_original_and_spare_time(self):
        """Verify choosing ``keep_plan`` preserves the original schedule and leaves freed slots open."""
        s = example()
        early_finish(s)
        before = deepcopy(s['calendar'])
        decide(s, 'keep_plan', s['proposal']['id'], TODAY)
        self.assertEqual(s['calendar'], before)
        self.assertEqual(len([cell for cell in available_cells(s, TODAY) if cell[0] == D0]), 3)
        self.assertIsNone(s['proposal'])

    def test_stale_confirmation_rejected(self):
        """Verify ``decide()`` raises ``ValueError`` when proposal ID or current date is stale."""
        s = example()
        early_finish(s)
        # Wrong revision ID or next-day confirmation must be rejected
        with self.assertRaises(ValueError):
            decide(s, 'confirm_move', 'stale', TODAY)
        with self.assertRaises(ValueError):
            decide(s, 'confirm_move', s['proposal']['id'], TODAY + timedelta(days=1))

    def test_pending_move_and_clock_logs_survive_restart(self):
        """Verify pending move proposals and timestamped work logs persist across save/load cycles."""
        s = example()
        early_finish(s)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'test.json'
            save_state(path, s)
            restored, _ = load_state(path, TODAY)
            initialize(restored, TODAY)
            self.assertEqual(restored, s)
            decide(restored, 'confirm_move', restored['proposal']['id'], TODAY)
            self.assertEqual(restored['calendar'][0]['date'], D0)

    def test_new_day_discards_expired_proposal(self):
        """Verify advancing to the next calendar day discards stale proposals and rolls schedule forward."""
        s = example()
        early_finish(s)
        initialize(s, TODAY + timedelta(days=1))
        self.assertIsNone(s['proposal'])
        self.assertTrue(all(b['date'] >= D1 for b in s['calendar']))

    def test_no_followup_leaves_free_time_without_proposal(self):
        """Verify finishing the sole remaining task leaves spare slots without generating an empty proposal."""
        s = example()
        s['tasks'] = s['tasks'][:1]
        initialize(s, TODAY)
        early_finish(s)
        self.assertEqual(s['calendar'], [])
        self.assertIsNone(s['proposal'])
        self.assertEqual(len([cell for cell in available_cells(s, TODAY) if cell[0] == D0]), 3)

    def test_half_hour_windows_overlap_and_clock_validation(self):
        """Verify clock boundary parsing and rejection of overlapping custom availability windows."""
        for bad in ['18:15', '24:30', '25:00', 'abc']:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                clock(bad)
        self.assertEqual(clock('24:00'), 1440)
        s = state([])
        # Overlapping windows (18:00–20:00 and 19:30–21:00) must fail without mutating state
        data = form(**{f'{D0}_start_0': '18:00', f'{D0}_end_0': '20:00', f'{D0}_start_1': '19:30', f'{D0}_end_1': '21:00'})
        with self.assertRaises(ValueError):
            update_windows(s, data, TODAY)
        self.assertEqual(s['availability'], {})
        # Adjusting second window start to 20:00 makes them adjacent and valid (180 min total)
        data[f'{D0}_start_1'] = ['20:00']
        update_windows(s, data, TODAY)
        self.assertEqual(s['capacity'][D0], 180)
        self.assertEqual(s['availability'][D1], [])

    def test_actual_overlap_and_midnight_rejected(self):
        """Verify ``record_clock`` rejects overlapping work sessions and sessions crossing 24:00."""
        s = example()
        early_finish(s)
        with self.assertRaises(ValueError):
            record_clock(s, form(actual='0.5', session_start='18:00'), TODAY)
        with self.assertRaises(ValueError):
            record_clock(s, form(actual='1', session_start='23:30'), TODAY)

    def test_current_time_cutoff_and_goal_exclusion(self):
        """Verify ``not_before`` excludes past slots on ``today`` and goal tasks are never auto-placed."""
        s = example()
        s['tasks'].append(task('goal', kind='goal'))
        plan, _ = candidate(s, TODAY, not_before=1110)
        self.assertTrue(all(b['start'] >= 1110 for b in plan if b['date'] == D0))
        self.assertTrue(all(b['task_id'] != 'goal' for b in plan))
        self.assertEqual(len(cells(plan)), sum((b['end'] - b['start']) // 30 for b in plan))

    def test_map_and_calendar_preview_markup(self):
        """Verify schedule preview renders solid origin and ghost destination blocks until confirmed."""
        s = example()
        early_finish(s)
        with patch('android.runtime.main.today_hk', return_value=TODAY):
            map_page = render(s)
            calendar = render(s, query={'tab': ['schedule']})
        # Before confirmation: preview shows both solid origin and ghost destination blocks
        self.assertIn('map-point', map_page)
        self.assertNotIn('class="task"', map_page)
        self.assertIn('solid origin', calendar)
        self.assertIn('ghost destination', calendar)
        self.assertIn('確認前移', calendar)
        # After confirmation: ghost markers disappear
        decide(s, 'confirm_move', s['proposal']['id'], TODAY)
        with patch('android.runtime.main.today_hk', return_value=TODAY):
            confirmed = render(s, query={'tab': ['schedule']})
        self.assertNotIn('ghost destination', confirmed)
        self.assertNotIn('ghost origin', confirmed)

    def test_midnight_zero_boundary_and_reversed_window_rejected(self):
        """Boundary test: ``00:00``/``24:00`` round-trip cleanly with ``stamp()``, and ``start >= end`` windows fail."""
        self.assertEqual(clock('00:00'), 0)
        self.assertEqual(stamp(0), '00:00')
        self.assertEqual(stamp(1440), '24:00')

        s = state([])
        for bad_start, bad_end in [('18:00', '18:00'), ('19:00', '18:00')]:
            with self.subTest(bad_start=bad_start, bad_end=bad_end), self.assertRaises(ValueError):
                update_windows(s, form(**{f'{D0}_start_0': bad_start, f'{D0}_end_0': bad_end}), TODAY)

        # Full-day 00:00–24:00 custom window must yield 1440 minutes of capacity
        update_windows(s, form(**{f'{D0}_start_0': '00:00', f'{D0}_end_0': '24:00'}), TODAY)
        self.assertEqual(s['capacity'][D0], 1440)

    def test_legacy_duration_only_work_log_consumes_leading_window_slots(self):
        """Edge case: v2 work-log entries lacking ``start``/``end`` consume leading 30-min cells of availability."""
        s = state([])
        s['availability'] = {D0: [[600, 720]]}  # 10:00–12:00 (slots 600, 630, 660, 690)
        s['work_log'] = [dict(task_id='legacy', title='Legacy Log', date=D0, minutes=60, finished=False)]
        self.assertEqual(occupied(s, D0), {600, 630})

    def test_blocks_from_cells_merges_adjacent_and_splits_disjoint_or_cross_day(self):
        """Boundary test: adjacent 30-min cells merge into one block while gaps and day boundaries split blocks."""
        mapping = {
            (D0, 540): 'A',
            (D0, 570): 'A',  # Adjacent -> merges to 540–600
            (D0, 630): 'A',  # Gap at 600 -> separate block 630–660
            (D0, 1410): 'A',  # Ends at 24:00
            (D1, 0): 'A',  # Next day 00:00 -> separate block
        }
        merged = blocks_from_cells(mapping)
        self.assertEqual(
            merged,
            [
                dict(task_id='A', date=D0, start=540, end=600),
                dict(task_id='A', date=D0, start=630, end=660),
                dict(task_id='A', date=D0, start=1410, end=1440),
                dict(task_id='A', date=D1, start=0, end=30),
            ],
        )


if __name__ == '__main__':
    unittest.main()