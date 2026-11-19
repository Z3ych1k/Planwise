"""Input boundary regression tests using temporary data and loopback HTTP only.

This module verifies form payload normalization, ISO-8601 date parsing error
sanitization, read-only recovery when loading deeply nested corrupted JSON
files, deployment packaging inclusions, and end-to-end Android loopback HTTP
input validation.
"""
from datetime import date
from http.client import HTTPConnection
import json
from pathlib import Path
import tempfile
from threading import Thread
import unittest
from urllib.parse import urlencode

from android.runtime.main import make_server, TOKEN
from storage import empty_state, save_state, load_state
from validation import normalize_fields, parse_date


class ValidationTests(unittest.TestCase):
    """Unit and packaging regression tests for the ``validation`` module."""

    def test_scalar_and_numeric_values_keep_existing_form_contract(self):
        """Verify scalar values become 1-item string lists while multi-value keys stay lists."""
        self.assertEqual(normalize_fields({'title': 'x', 'hours': 0.5, 'workdays': []}),
                         {'title': ['x'], 'hours': ['0.5'], 'workdays': []})

    def test_structural_limits_and_unsupported_values(self):
        """Reject non-dicts, oversized payloads, duplicate scalars, booleans, and non-finite floats."""
        for fields in [None, [], {'title': []}, {'title': ['a', 'b']},
                       {'title': True}, {'title': None}, {'hours': float('nan')},
                       {'hours': float('inf')}, {'weekdays': list(range(21))},
                       {str(i): 'x' for i in range(101)}, {1: 'x'}]:
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                normalize_fields(fields)

    def test_valid_and_invalid_dates(self):
        """Accept valid leap-year ISO dates and raise localized ValueError for invalid inputs."""
        self.assertEqual(parse_date('2028-02-29'), date(2028, 2, 29))
        for value in ['', '2026-02-30', '2026-13-01', 'text', None, []]:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, '日期無效'):
                parse_date(value)

    def test_deeply_nested_local_file_is_preserved_and_opens_read_only(self):
        """Ensure excessively nested JSON triggers read-only server mode without overwriting disk."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'plan.json'
            original = '['*2000+'0'+']'*2000
            path.write_text(original, encoding='utf-8')
            with self.assertRaisesRegex(ValueError, '原檔已保留'):
                load_state(path, date(2026, 11, 14))
            server = make_server(path)
            try:
                self.assertTrue(server.read_only)
                self.assertEqual(path.read_text(encoding='utf-8'), original)
            finally:
                server.server_close()

    def test_packaging_includes_shared_validation_module(self):
        """Check that Docker and Android packaging manifests bundle ``validation.py``."""
        root = Path(__file__).parent
        self.assertIn('!validation.py', (root/'.dockerignore').read_text())
        self.assertIn('validation.py', (root/'nas/Dockerfile').read_text())
        self.assertIn('validation.py', (root/'android/build-apk.sh').read_text())


class AndroidInputTests(unittest.TestCase):
    """Loopback HTTP integration tests for Android form input sanitization."""

    def setUp(self):
        """Start an isolated loopback HTTP server backed by a temporary state file."""
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name)/'plan.json'
        save_state(self.path, empty_state())
        self.server = make_server(self.path)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        """Shut down the loopback server and clean up temporary test storage."""
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.directory.cleanup()

    def post(self, pairs):
        """Send an authenticated URL-encoded POST request to the test server.

        Args:
            pairs (list[tuple[str, str]]): Form key-value pairs to submit.

        Returns:
            tuple[int, dict]: HTTP status code and parsed JSON response body.
        """
        connection = HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        try:
            connection.request('POST', '/', urlencode([('token', TOKEN)]+pairs),
                               {'Content-Type': 'application/x-www-form-urlencoded', 'Accept': 'application/json'})
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def test_duplicate_scalar_is_rejected_and_file_unchanged(self):
        """Reject duplicate single-value form keys with HTTP 400 and leave disk untouched."""
        before = self.path.read_bytes()
        status, body = self.post([('action', 'save'), ('title', 'first'), ('title', 'second')])
        self.assertEqual(status, 400)
        self.assertFalse(body['ok'])
        self.assertEqual(self.path.read_bytes(), before)

    def test_bad_date_then_valid_save_and_reload(self):
        """Verify invalid dates fail cleanly before a subsequent valid save persists."""
        base = [('action', 'save'), ('title', 'Essay'), ('kind', 'deadline'),
                ('hours', '1'), ('important', 'yes')]
        before = self.path.read_bytes()
        status, body = self.post(base+[('due', '2026-02-30')])
        self.assertEqual(status, 400)
        self.assertIn('日期無效', body['error'])
        self.assertEqual(self.path.read_bytes(), before)
        status, body = self.post(base+[('due', '2026-11-30')])
        self.assertEqual(status, 200)
        self.assertTrue(body['ok'])
        reloaded, _ = load_state(self.path, date(2026, 11, 14))
        self.assertEqual(reloaded['tasks'][0]['title'], 'Essay')


class EdgeCaseAndBoundaryTests(unittest.TestCase):
    """Comprehensive boundary, extreme-value, and special-input tests across modules."""

    def test_clock_and_duration_exact_boundaries(self):
        """Verify 00:00/24:00 endpoints, non-30-min steps, and 0..1000h bounds."""
        from time_slots import parse_clock
        from planner import minutes

        # Valid boundaries: 00:00 -> 0, 24:00 -> 1440
        self.assertEqual(parse_clock('00:00', 'missing', 'invalid'), 0)
        self.assertEqual(parse_clock('24:00', 'missing', 'invalid'), 1440)

        # Invalid clock boundaries: 24:30, 25:00, 09:15, negative, malformed
        for bad_clock in ['24:30', '25:00', '09:15', '-01:00', '12:60']:
            with self.subTest(bad_clock=bad_clock), self.assertRaisesRegex(ValueError, 'invalid'):
                parse_clock(bad_clock, 'missing', 'invalid')
        # Non-HH:MM string without colon raises missing_message
        with self.assertRaisesRegex(ValueError, 'missing'):
            parse_clock('abc', 'missing', 'invalid')

        # Valid duration boundaries: 0.0 -> 0, 0.5 -> 30, 1000.0 -> 60000
        self.assertEqual(minutes('0'), 0)
        self.assertEqual(minutes('0.5'), 30)
        self.assertEqual(minutes('1000'), 60000)

        # Invalid durations: negative, >1000, quarter-hour, NaN, Inf
        for bad_hours in ['-0.5', '1000.5', '0.25', 'nan', 'inf', None]:
            with self.subTest(bad_hours=bad_hours), self.assertRaises(ValueError):
                minutes(bad_hours)

    def test_title_length_and_daily_24h_capacity_limits(self):
        """Verify exact 100-char title limit and 24-hour (1440 min) daily caps."""
        from planner import mutate

        state = empty_state()
        today = date(2026, 11, 14)

        # 100 chars succeeds; 101 chars raises ValueError
        mutate(state, {
            'action': ['save'],
            'title': ['A' * 100],
            'course': ['C' * 60],
            'kind': ['deadline'],
            'due': ['2026-11-20'],
            'hours': ['24'],
            'important': ['yes'],
        }, today)
        self.assertEqual(len(state['tasks']), 1)

        with self.assertRaises(ValueError):
            mutate(state, {
                'action': ['save'],
                'title': ['A' * 101],
                'course': [''],
                'kind': ['goal'],
                'important': ['no'],
            }, today)

        # Logging exactly 24h on one day succeeds; adding another 0.5h fails
        task_id = state['tasks'][0]['id']
        mutate(state, {'action': ['progress'], 'id': [task_id], 'actual': ['24'], 'finished': ['no']}, today)
        with self.assertRaises(ValueError):
            mutate(state, {'action': ['progress'], 'id': [task_id], 'actual': ['0.5'], 'finished': ['no']}, today)

    def test_holiday_boundary_and_outside_published_years_fallback(self):
        """Verify HK gazetted holidays in 2026/2027 and weekday-only fallback in 2028+."""
        from holidays import holiday_name, is_workday

        # 2026-10-01 is National Day (Thursday -> holiday, not workday)
        self.assertEqual(holiday_name(date(2026, 10, 1)), '國慶日')
        self.assertFalse(is_workday(date(2026, 10, 1)))

        # 2028-10-01 is a Sunday (outside 2026-2027 catalog -> falls back to '星期日')
        self.assertEqual(holiday_name(date(2028, 10, 1)), '星期日')
        # 2028-10-02 is Monday (outside published years -> treated as regular workday)
        self.assertTrue(is_workday(date(2028, 10, 2)))

    def test_i18n_protects_user_content_and_escapes_special_characters(self):
        """Ensure user-generated HTML/text with UI keywords is never translated or corrupted."""
        from i18n import CATALOG, localize_html

        source_phrase, targets = next(iter(CATALOG.items()))
        en_phrase = targets[1]
        html = (
            f'<html lang="zh-Hant"><body><button>{source_phrase}</button>'
            f'<div data-user>{source_phrase} &amp; 保留</div>'
            f'<textarea>{source_phrase}</textarea></body></html>'
        )
        localized = localize_html(html, 'en')
        self.assertIn('<html lang="en">', localized)
        self.assertIn(f'<button>{en_phrase}</button>', localized)
        # User text inside data-user and textarea must remain untouched
        self.assertIn(f'<div data-user>{source_phrase} &amp; 保留</div>', localized)
        self.assertIn(f'<textarea>{source_phrase}</textarea>', localized)

    def test_v1_migration_asymmetric_rounding_boundaries(self):
        """Verify v1->v2 migration rounds task minutes up and capacity minutes down to 30m."""
        from storage import migrate

        v1_raw = {
            'version': 1,
            'tasks': [{
                'id': 't1',
                'title': 'Legacy Task',
                'course': 'CS',
                'start': '',
                'due': '2026-11-20',
                'minutes': 15,      # Should round UP to 30
                'important': True,
                'completed': False,
                'completed_on': '',
            }],
            'capacity': {
                '2026-11-14': 45,   # Should round DOWN to 30
                '2026-11-15': 29,   # Should round DOWN to 0
            },
        }
        migrated = migrate(v1_raw)
        self.assertEqual(migrated['version'], 2)
        self.assertEqual(migrated['tasks'][0]['minutes'], 30)
        self.assertEqual(migrated['capacity']['2026-11-14'], 30)
        self.assertEqual(migrated['capacity']['2026-11-15'], 0)

    def test_urgent_private_borrowing_3day_cutoff_and_drag_midnight_guard(self):
        """Verify private-time borrowing stops at day +4 and drag-and-drop blocks midnight overflow."""
        from events import save_event
        from timetable import refresh, move_block

        today = date(2026, 11, 14)
        state = empty_state()
        state['borrow_private'] = True
        state['time_model'] = 'custom'
        # Day +3 (Nov 17) and Day +4 (Nov 18) each have 1h capacity fully covered by a private event
        for offset in (3, 4):
            day_str = (today + date.resolution * offset).isoformat()
            state['availability'][day_str] = [[540, 600]]
            state['capacity'][day_str] = 60
            save_event(state, {
                'title': ['Private Block'],
                'category': ['private'],
                'date': [day_str],
                'event_start': ['09:00'],
                'event_end': ['10:00'],
                'repeat': ['none'],
            })

        # Task due on Day +3 CAN borrow private slot; task due on Day +4 CANNOT
        state['tasks'] = [
            dict(id='urgent3', title='Due Day 3', course='', kind='deadline', start='2026-11-17', due='2026-11-17', minutes=60, important=True, completed=False, completed_on=''),
            dict(id='later4', title='Due Day 4', course='', kind='deadline', start='2026-11-18', due='2026-11-18', minutes=60, important=True, completed=False, completed_on=''),
        ]
        refresh(state, today)
        scheduled_ids = {b['task_id'] for b in state['calendar']}
        self.assertIn('urgent3', scheduled_ids)
        self.assertNotIn('later4', scheduled_ids)

        # Dragging a 60-min block to 23:30 (would end at 24:30 > 1440) must be rejected
        block = state['calendar'][0]
        with self.assertRaisesRegex(ValueError, '不能拖過午夜'):
            move_block(state, {
                'id': [block['task_id']],
                'source_date': [block['date']],
                'source_start': ['09:00'],
                'source_end': ['10:00'],
                'new_date': ['2026-11-17'],
                'new_start': ['23:30'],
            }, today)

    def test_monthly_event_on_31st_skips_shorter_months_safely(self):
        """Ensure monthly recurrence starting on the 31st does not fail on 28/30-day months."""
        from events import save_event, occurrences

        state = empty_state()
        save_event(state, {
            'title': ['Month-End Review'],
            'category': ['fixed'],
            'date': ['2026-01-31'],
            'event_start': ['10:00'],
            'event_end': ['11:00'],
            'repeat': ['monthly'],
        })
        blocks = occurrences(state, date(2026, 1, 31), date(2026, 4, 30))
        self.assertEqual([b['date'] for b in blocks], ['2026-01-31', '2026-03-31'])

    def test_overlogged_work_clamps_remaining_free_capacity_to_zero(self):
        """Verify logging more hours than planned capacity clamps free time to 0 rather than negative."""
        from planner import schedule

        today = date(2026, 11, 14)
        day_str = today.isoformat()
        state = empty_state()
        state['capacity'][day_str] = 60
        state['work_log'].append(dict(task_id='x', title='Extra Study', date=day_str, minutes=180, finished=False))
        _, free, _ = schedule(state, today)
        self.assertEqual(free[day_str], 0)

    def test_storage_refuses_overwriting_corrupted_file_and_rejects_overlapping_backup(self):
        """Ensure save_state protects corrupted files and import_state rejects overlapping blocks."""
        from storage import import_state

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'plan.json'
            path.write_text('[1, 2, 3]', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, '原資料格式已改變'):
                save_state(path, empty_state())
            # Original non-dict file content must remain intact
            self.assertEqual(path.read_text(encoding='utf-8'), '[1, 2, 3]')

        # Backup envelope with wrong version or overlapping calendar blocks must fail
        bad_version = json.dumps({'format': 'planwise-backup', 'backup_version': 2, 'data': empty_state()})
        with self.assertRaisesRegex(ValueError, '備份檔格式不正確'):
            import_state(bad_version)

        overlap_state = empty_state()
        overlap_state['tasks'].append(dict(
            id='t1', title='Task 1', course='', kind='deadline', start='',
            due='2026-11-20', minutes=120, important=True, completed=False, completed_on=''
        ))
        overlap_state['calendar'] = [
            {'task_id': 't1', 'date': '2026-11-14', 'start': 540, 'end': 600},
            {'task_id': 't1', 'date': '2026-11-14', 'start': 570, 'end': 630},
        ]
        with self.assertRaisesRegex(ValueError, '備份檔格式不正確'):
            import_state(json.dumps(overlap_state))

    def test_duplicate_or_off_schedule_occurrence_cancellation_rejected(self):
        """Verify cancelling an already-cancelled or non-matching occurrence date raises ValueError."""
        from events import save_event, cancel_occurrence

        state = empty_state()
        save_event(state, {
            'title': ['Weekday Standup'],
            'category': ['fixed'],
            'date': ['2026-11-16'],  # Monday
            'event_start': ['09:00'],
            'event_end': ['09:30'],
            'repeat': ['workdays'],
        })
        event_id = state['events'][0]['id']

        # Saturday (2026-11-21) does not match a workdays rule
        with self.assertRaisesRegex(ValueError, '找不到這一次重複事項'):
            cancel_occurrence(state, {'id': [event_id], 'occurrence_date': ['2026-11-21']})

        # First cancellation succeeds; second cancellation on the same date must fail
        cancel_occurrence(state, {'id': [event_id], 'occurrence_date': ['2026-11-16']})
        with self.assertRaisesRegex(ValueError, '這一次事項已移除'):
            cancel_occurrence(state, {'id': [event_id], 'occurrence_date': ['2026-11-16']})

    def test_stale_cross_day_or_replayed_move_proposal_is_rejected(self):
        """Ensure move proposals cannot be confirmed after midnight rollover or replayed twice."""
        from timetable import refresh, decide

        today = date(2026, 11, 14)
        tomorrow = date(2026, 11, 15)
        state = empty_state()
        state['tasks'] = [
            dict(id='t_later', title='Later', course='', kind='deadline', start='2026-11-14', due='2026-11-20', minutes=60, important=False, completed=False, completed_on=''),
        ]
        refresh(state, today, propose=False)
        # Add an urgent earlier-deadline task to trigger a move proposal
        state['tasks'].append(
            dict(id='t_urgent', title='Urgent', course='', kind='deadline', start='2026-11-14', due='2026-11-14', minutes=1440, important=True, completed=False, completed_on='')
        )
        refresh(state, today, propose=True)
        self.assertIsNotNone(state['proposal'])
        rev = state['proposal']['id']

        # Confirming on the next day (stale date) must fail
        with self.assertRaisesRegex(ValueError, '前移建議已更新'):
            decide(state, 'confirm_move', rev, tomorrow)

        # Confirming on the valid day succeeds, and replaying the same revision fails
        decide(state, 'confirm_move', rev, today)
        self.assertIsNone(state['proposal'])
        with self.assertRaisesRegex(ValueError, '前移建議已更新'):
            decide(state, 'confirm_move', rev, today)

    def test_completed_task_blocks_subsequent_edits_and_progress_logs(self):
        """Verify completed tasks cannot be edited or logged again via planner.mutate."""
        from planner import mutate

        today = date(2026, 11, 14)
        state = empty_state()
        mutate(state, {
            'action': ['save'],
            'title': ['Finish Report'],
            'course': ['CS'],
            'kind': ['deadline'],
            'due': ['2026-11-15'],
            'hours': ['1'],
            'important': ['yes'],
        }, today)
        task_id = state['tasks'][0]['id']

        # Logging full 1 hour automatically marks the deadline task completed
        mutate(state, {'action': ['progress'], 'id': [task_id], 'actual': ['1'], 'finished': ['no']}, today)
        self.assertTrue(state['tasks'][0]['completed'])

        # Further progress logging or editing must both raise ValueError
        with self.assertRaisesRegex(ValueError, '這份任務已完成'):
            mutate(state, {'action': ['progress'], 'id': [task_id], 'actual': ['0.5'], 'finished': ['no']}, today)
        with self.assertRaisesRegex(ValueError, '這份任務已完成'):
            mutate(state, {
                'action': ['save'],
                'id': [task_id],
                'title': ['Reopen Report'],
                'course': ['CS'],
                'kind': ['deadline'],
                'due': ['2026-11-16'],
                'hours': ['2'],
                'important': ['yes'],
            }, today)

    def test_translations_catalog_schema_and_completeness_across_all_locales(self):
        """Verify every entry in translations.json provides non-empty zh-Hans and en strings."""
        from i18n import CATALOG

        self.assertGreater(len(CATALOG), 0)
        for source_key, targets in CATALOG.items():
            with self.subTest(source_key=source_key):
                self.assertIsInstance(source_key, str)
                self.assertTrue(source_key.strip())
                self.assertIsInstance(targets, list)
                self.assertEqual(len(targets), 2, f'Missing zh-Hans or en entry for {source_key!r}')
                self.assertTrue(all(isinstance(t, str) and t.strip() for t in targets))

    def test_fixed_event_single_move_forbidden_and_7day_window_enforced(self):
        """Ensure fixed events cannot move single occurrences and private moves enforce [today, today+6]."""
        from events import save_event, move_occurrence

        today = date(2026, 11, 14)
        state = empty_state()
        save_event(state, {
            'title': ['Fixed Lecture'],
            'category': ['fixed'],
            'date': ['2026-11-14'],
            'event_start': ['10:00'],
            'event_end': ['11:00'],
            'repeat': ['daily'],
        })
        fixed_id = state['events'][0]['id']
        with self.assertRaisesRegex(ValueError, '固定事項不能移動'):
            move_occurrence(state, {
                'id': [fixed_id],
                'occurrence_date': ['2026-11-14'],
                'new_date': ['2026-11-15'],
                'new_start': ['14:00'],
            }, today)

        save_event(state, {
            'title': ['Private Gym'],
            'category': ['private'],
            'date': ['2026-11-14'],
            'event_start': ['18:00'],
            'event_end': ['19:00'],
            'repeat': ['daily'],
        })
        private_id = state['events'][1]['id']
        # Moving to yesterday (today - 1) or Day +7 (outside 7-day horizon) must fail
        for out_of_range_day in ['2026-11-13', '2026-11-21']:
            with self.subTest(new_date=out_of_range_day), self.assertRaisesRegex(ValueError, '未來七天內'):
                move_occurrence(state, {
                    'id': [private_id],
                    'occurrence_date': ['2026-11-14'],
                    'new_date': [out_of_range_day],
                    'new_start': ['19:00'],
                }, today)

    def test_android_server_rejects_invalid_token_and_oversized_request_body(self):
        """Verify loopback HTTP endpoint blocks unauthorized tokens and oversized payloads."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'plan.json'
            save_state(path, empty_state())
            server = make_server(path)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                conn = HTTPConnection('127.0.0.1', server.server_port, timeout=5)
                conn.request(
                    'POST', '/',
                    urlencode([('token', 'wrong-token'), ('action', 'save'), ('title', 'Hack')]),
                    {'Content-Type': 'application/x-www-form-urlencoded', 'Accept': 'application/json'}
                )
                resp = conn.getresponse()
                self.assertIn(resp.status, (400, 403))
                conn.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

if __name__ == '__main__':
    unittest.main()