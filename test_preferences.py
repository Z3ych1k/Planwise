"""Behavioral and boundary checks for preferences, effort, holiday rules, and portable backups.

Verifies Hong Kong 2026–2027 statutory holidays, workday/holiday recurrence complements,
goal progress dot rendering, portable backup round-trips, strict import validation,
single-pass HTML localization with user-data isolation, and responsive day/week grids.
"""
from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from android.runtime.main import render, task_bubble
from events import occurrences, save_event
from holidays import HOLIDAYS, holiday_name, is_workday
from i18n import localize_html, translate
from planner import goal_progress, mutate
from storage import empty_state, export_state, import_state, load_state, save_state
from test_events import event, free_state
from test_planner import TODAY, form, task


class PreferencesTests(unittest.TestCase):
    """Tests for holiday calendars, goal effort tracking, backups, i18n, and mobile grids."""

    def test_hk_2026_substitute_holidays_and_2027_new_year(self):
        """Verify all 34 gazetted 2026–2027 HK holidays are recognized as non-workdays."""
        self.assertEqual(len(HOLIDAYS), 34)
        for day in ['2026-04-06', '2026-04-07', '2026-05-25', '2026-10-19', '2027-02-09', '2027-12-27']:
            dt = date.fromisoformat(day)
            self.assertTrue(holiday_name(dt))
            self.assertFalse(is_workday(dt))
        self.assertTrue(is_workday(date(2026, 4, 8)))
        self.assertFalse(is_workday(date(2026, 4, 5)))

    def test_workday_and_holiday_rules_are_complements_with_custom_workdays(self):
        """Verify ``workdays`` and ``holidays`` recurrence rules partition dates cleanly under custom workweeks."""
        s = free_state()
        s['events'] = [event('work', day='2026-12-24', repeat='workdays'), event('rest', day='2026-12-24', repeat='holidays')]
        rows = occurrences(s, date(2026, 12, 24), date(2026, 12, 28))
        self.assertEqual([(r['event_id'], r['date']) for r in rows], [('work', '2026-12-24'), ('rest', '2026-12-25'), ('rest', '2026-12-26'), ('rest', '2026-12-27'), ('work', '2026-12-28')])
        s['workdays'] = [5]
        rows = occurrences(s, date(2026, 11, 6), date(2026, 11, 8))
        self.assertEqual(rows, [])  # Before the series start.
        s['events'][0]['date'] = s['events'][1]['date'] = '2026-11-06'
        rows = occurrences(s, date(2026, 11, 6), date(2026, 11, 8))
        self.assertEqual([(r['event_id'], r['date']) for r in rows], [('rest', '2026-11-06'), ('work', '2026-11-07'), ('rest', '2026-11-08')])

    def test_new_repeat_options_round_trip(self):
        """Verify ``workdays`` and ``holidays`` recurrence rules survive backup export and import."""
        for rule in ('workdays', 'holidays'):
            s = empty_state()
            save_event(s, form(action='save_event', title='repeat', category='fixed', date='2026-11-06', event_start='09:00', event_end='10:00', repeat=rule))
            self.assertEqual(import_state(export_state(s)), s)

    def test_goal_effort_fills_without_completing_and_survives_restart(self):
        """Verify logging effort on a goal updates progress ratio up to 1.0 without auto-completing."""
        s = empty_state()
        mutate(s, form(action='save', title='N1', kind='goal', important='yes', target_hours='2'), TODAY)
        goal = s['tasks'][0]
        self.assertEqual(goal_progress(s, goal), (0, 120, 0))
        mutate(s, form(action='progress', id=goal['id'], actual='0.5'), TODAY)
        self.assertEqual(goal_progress(s, goal), (30, 120, .25))
        mutate(s, form(action='progress', id=goal['id'], actual='3'), TODAY)
        self.assertEqual(goal_progress(s, goal), (210, 120, 1))
        self.assertFalse(goal['completed'])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'state.json'
            save_state(path, s)
            loaded, _ = load_state(path, TODAY)
        self.assertEqual(goal_progress(loaded, loaded['tasks'][0]), (210, 120, 1))

    def test_goal_svg_contains_partial_fill_and_clear_reference_label(self):
        """Verify rendered goal SVG progress bar and detail bubble reflect 50% logged effort."""
        s = empty_state()
        mutate(s, form(action='save', title='N1', kind='goal', important='yes', target_hours='2'), TODAY)
        mutate(s, form(action='progress', id=s['tasks'][0]['id'], actual='1'), TODAY)
        html = render(s)
        self.assertIn('class="goal-fill"', html)
        self.assertIn('height="7"', html)
        self.assertIn('50%', task_bubble(s, TODAY, s['tasks'][0]['id'], False, 'map'))
        self.assertFalse(s['tasks'][0]['completed'])

    def test_complete_backup_round_trip_and_legacy_raw_json(self):
        """Verify both wrapped ``planwise-backup`` envelopes and raw v2 JSON restore identically."""
        s = free_state([task()])
        s.update(language='en', workdays=[1, 2, 3, 4, 5], borrow_private=True)
        s['events'] = [event(repeat='holidays')]
        s['pins'] = [dict(task_id=s['tasks'][0]['id'], date=TODAY.isoformat(), start=600, end=630)]
        s['calendar'] = deepcopy(s['pins'])
        self.assertEqual(import_state(export_state(s)), s)
        self.assertEqual(import_state(json.dumps(s)), s)

    def test_invalid_imports_do_not_modify_original(self):
        """Verify malformed JSON, unsupported locales, boolean weekday traps, and bad backup versions raise ``ValueError``."""
        s = empty_state()
        before = deepcopy(s)
        invalid = [
            'no json',
            '[]',
            'null',
            json.dumps(dict(s, language='fr')),
            json.dumps(dict(s, events=[42])),
            json.dumps(dict(s, workdays=[True])),
            json.dumps(dict(format='planwise-backup', backup_version=9, data=s)),
        ]
        for text in invalid:
            with self.subTest(text=text), self.assertRaises(ValueError):
                import_state(text)
        self.assertEqual(s, before)

    def test_localization_preserves_user_text_and_input_values(self):
        """Verify HTML localizer translates static UI labels while protecting ``data-user``, inputs, and textareas."""
        html = '<p>任務地圖</p><b data-user>重要事項：任務地圖 &amp; N1</b><input name="title" value="任務地圖"><textarea>任務地圖</textarea>'
        en = localize_html(html, 'en')
        self.assertIn('<p>Task map</p>', en)
        self.assertIn('重要事項：任務地圖 &amp; N1', en)
        self.assertIn('value="任務地圖"', en)
        self.assertIn('<textarea>任務地圖</textarea>', en)
        self.assertEqual(translate('任務地圖', 'zh-Hans'), '任务地图')

    def test_three_languages_all_tabs_and_bubble(self):
        """Verify all three locales (``zh-Hant``, ``zh-Hans``, ``en``) render consistently across tabs and bubbles."""
        s = empty_state()
        for language, label in [('zh-Hant', '資料導入／導出'), ('zh-Hans', '数据导入／导出'), ('en', 'Import / export data')]:
            s['language'] = language
            for tab in ('map', 'schedule', 'events'):
                html = render(s, query={'tab': [tab]})
                self.assertIn('lang="' + language + '"', html)
                self.assertIn('/app.js', html)
                if tab == 'events':
                    self.assertIn(label, html)
        s['language'] = 'en'
        en = localize_html(task_bubble(s, TODAY, '', True, 'map'), 'en')
        self.assertIn('Reference hours for a full dot', en)
        self.assertNotIn('參考', en)

    def test_mobile_grid_is_full_day_and_day_navigation_exists(self):
        """Verify single-day schedule mode renders full 00:00–24:00 grid with week-view toggle link."""
        html = render(empty_state(), query={'tab': ['schedule'], 'span': ['day']})
        self.assertIn('24:00', html)
        self.assertIn('00:00', html)
        self.assertIn('single-day', html)
        self.assertEqual(html.count('class="day-heading '), 1)
        self.assertIn('span=week', html)

    def test_post_2027_holiday_fallback_and_empty_workdays_boundary(self):
        """Boundary test: years beyond 2027 fall back to weekday rules, and empty ``workdays=[]`` treats every day as rest."""
        # 2028-01-01 is Saturday (not in 2026-2027 gazette); 2028-01-02 is Sunday
        self.assertEqual(holiday_name(date(2028, 1, 1)), '')
        self.assertEqual(holiday_name(date(2028, 1, 2)), '星期日')
        self.assertTrue(is_workday(date(2028, 1, 3)))  # Monday
        self.assertFalse(is_workday(date(2028, 1, 3), weekdays=[]))

    def test_goal_target_hours_minimum_half_hour_boundary(self):
        """Boundary test: goal ``target_hours`` accepts 0.5h (30 min) minimum and rejects 0h to prevent zero division."""
        s = empty_state()
        with self.assertRaises(ValueError):
            mutate(s, form(action='save', title='Zero Target', kind='goal', important='yes', target_hours='0'), TODAY)
        mutate(s, form(action='save', title='Min Target', kind='goal', important='yes', target_hours='0.5'), TODAY)
        self.assertEqual(s['tasks'][0]['target_minutes'], 30)

    def test_english_date_reformatting_and_zh_hant_passthrough(self):
        """Edge case: English localization reformats Chinese year/month/day headings while ``zh-Hant`` returns verbatim."""
        snippet = '<h2>2026 年 11 月</h2><span>11 月 19 日，</span>'
        self.assertEqual(localize_html(snippet, 'zh-Hant'), snippet)
        en_snippet = localize_html(snippet, 'en')
        self.assertIn('2026 / 11', en_snippet)
        self.assertIn('11 / 19, ', en_snippet)

    def test_client_messages_and_html_entities_preserved_during_localization(self):
        """Edge case: ``client_messages`` translates all catalog keys and ``localize_html`` preserves HTML entities."""
        msgs_en = client_messages('en')
        self.assertTrue(len(msgs_en) > 0)
        self.assertEqual(msgs_en['任務地圖'], 'Task map')

        raw_html = '<!DOCTYPE html><input placeholder="任務地圖"/><span>&nbsp;&#39;任務地圖&#39;</span>'
        localized = localize_html(raw_html, 'en')
        self.assertIn('<!DOCTYPE html>', localized)
        self.assertIn('placeholder="Task map"', localized)
        self.assertIn('&nbsp;&#39;Task map&#39;', localized)


if __name__ == '__main__':
    unittest.main()