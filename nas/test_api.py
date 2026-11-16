"""Run: python -m unittest nas.test_api -v (all accounts/data are temporary)."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
import uuid
from unittest.mock import patch

from nas.application import create_app, HKT


class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.directory.name)/'seed.sqlite3')
        cls.config = dict(TESTING=True,DATABASE=cls.path,NOW=lambda:datetime(2026,11,12,9,0,tzinfo=HKT))
        cls.app = create_app(cls.config)
        cls.store = cls.app.extensions['store']
        cls.store.create_user('alice','correct-password-alice',True)
        cls.store.create_user('bob','correct-password-bob')
        cls.store.backup_to(Path(cls.directory.name)/'baseline.sqlite3')

    def setUp(self):
        self.local = tempfile.TemporaryDirectory()
        path = Path(self.local.name)/'test.sqlite3'
        path.write_bytes((Path(self.directory.name)/'baseline.sqlite3').read_bytes())
        self.app = create_app(dict(self.config,DATABASE=str(path)))
        self.store = self.app.extensions['store']
        self.client = self.app.test_client()
        self.login(self.client)

    def tearDown(self):
        self.local.cleanup()

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def login(self,client,name='alice'):
        return client.post('/api/login',json=dict(username=name,password='correct-password-'+name),headers={'X-Planwise-Client':'1'})

    def state(self,client=None):
        return (client or self.client).get('/api/state').get_json()

    def action(self,action,fields=None,client=None,version=None,key=None):
        client = client or self.client
        current = self.state(client)
        return client.post('/api/actions',json=dict(action=action,fields=fields or {},version=current['version'] if version is None else version,request_id=key or str(uuid.uuid4())),headers={'X-CSRF-Token':current['csrf'],'X-Planwise-Client':'1'})

    def task(self,title='Essay'):
        response = self.action('save',dict(title=title,course='INT6181',kind='deadline',due='2026-11-14',start='',hours='2',important='yes'))
        self.assertEqual(response.status_code,200,response.get_json())
        return response.get_json()['state']['tasks'][-1]['id']

    def test_cookie_is_http_only_and_no_password_in_snapshot(self):
        response = self.login(self.client)
        self.assertIn('HttpOnly',response.headers['Set-Cookie'])
        self.assertIn('SameSite=Strict',response.headers['Set-Cookie'])
        text = self.client.get('/api/state').get_data(as_text=True)
        self.assertNotIn('password_hash',text)
        self.assertNotIn('correct-password',text)

    def test_accounts_have_independent_plans_even_if_user_id_is_supplied(self):
        ident = self.task()
        bob = self.app.test_client(); self.login(bob,'bob')
        self.assertEqual(self.state(bob)['state']['tasks'],[])
        response = self.action('delete',{'id':ident,'user_id':self.state()['user']['id']},client=bob)
        self.assertEqual(response.status_code,400)
        self.assertEqual(len(self.state()['state']['tasks']),1)
        exported = bob.get('/api/export').get_json()
        self.assertEqual(exported['data']['tasks'],[])

    def test_same_account_on_two_devices_and_stale_version_conflict(self):
        device = self.app.test_client(); self.login(device)
        old = self.state(device)
        self.task('Desktop change')
        response = self.action('save_policy',{'borrow_private':'yes'},client=device,version=old['version'])
        self.assertEqual(response.status_code,409)
        self.assertEqual(response.get_json()['code'],'conflict')
        latest = self.state(device)
        self.assertEqual(latest['state']['tasks'][0]['title'],'Desktop change')
        self.assertFalse(latest['state']['borrow_private'])

    def test_simultaneous_writers_only_one_wins(self):
        devices = [self.app.test_client(),self.app.test_client()]
        for device in devices:self.login(device)
        states = [self.state(device) for device in devices]
        def save(i):
            return self.action('save_policy',{'borrow_private':'yes'},client=devices[i],version=states[i]['version']).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = sorted(pool.map(save,range(2)))
        self.assertEqual(results,[200,409])

    def test_csrf_and_cross_origin_are_rejected(self):
        current = self.state()
        data = dict(action='save_policy',fields={},version=current['version'],request_id=str(uuid.uuid4()))
        self.assertEqual(self.client.post('/api/actions',json=data,headers={'X-Planwise-Client':'1'}).status_code,403)
        self.assertEqual(self.client.post('/api/actions',json=data,headers={'X-Planwise-Client':'1','X-CSRF-Token':current['csrf'],'Origin':'http://evil.example'}).status_code,403)
        self.assertEqual(self.client.post('/api/login',data={'username':'alice'}).status_code,403)

    def test_unauthenticated_apis_and_export_are_blocked(self):
        client = self.app.test_client()
        for path in ('/api/state','/api/export','/api/offline'):
            self.assertEqual(client.get(path).status_code,401)
        with client.get('/') as response:
            self.assertEqual(response.status_code,200)
        self.assertEqual(client.get('/healthz').status_code,200)

    def test_retry_does_not_double_record_effort(self):
        ident = self.task(); current = self.state(); key = str(uuid.uuid4())
        fields = dict(id=ident,session_start='09:00',actual='0.5')
        first = self.action('progress',fields,version=current['version'],key=key)
        second = self.action('progress',fields,version=current['version'],key=key)
        self.assertEqual(first.status_code,200)
        self.assertEqual(second.status_code,200)
        self.assertTrue(second.get_json()['replayed'])
        self.assertEqual(len(self.state()['state']['work_log']),1)
        bad = self.action('progress',dict(fields,actual='1'),version=current['version'],key=key)
        self.assertEqual(bad.status_code,409)

    def test_bad_import_does_not_touch_live_plan(self):
        self.task(); before=self.state()
        response=self.action('import_data',dict(backup_json='{"tasks":[]}',replace_confirm='yes'))
        self.assertEqual(response.status_code,400)
        self.assertEqual(self.state()['state'],before['state'])
        self.assertEqual(self.state()['version'],before['version'])

    def test_import_export_and_preimport_backup(self):
        self.task('Original'); exported=self.client.get('/api/export').get_data(as_text=True)
        self.task('Later')
        response=self.action('import_data',dict(backup_json=exported,replace_confirm='yes'))
        self.assertEqual(response.status_code,200)
        self.assertEqual(len(self.state()['state']['tasks']),1)
        with closing(self.store.connect()) as db:
            backup=json.loads(db.execute('SELECT data FROM backups').fetchone()[0])
        self.assertEqual(len(backup['tasks']),2)

    def test_import_write_failure_rolls_back_plan_backup_and_request(self):
        self.task('Original')
        before = self.state()
        exported = self.client.get('/api/export').get_data(as_text=True)
        key = str(uuid.uuid4())
        original_save = self.store.save_plan_action

        def fail_after_write(*args):
            original_save(*args)
            raise sqlite3.OperationalError('simulated failure after writes')

        with patch.object(self.store, 'save_plan_action', side_effect=fail_after_write):
            response = self.action('import_data', dict(backup_json=exported, replace_confirm='yes'), key=key)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()['code'], 'storage')
        after = self.state()
        self.assertEqual(after['state'], before['state'])
        self.assertEqual(after['version'], before['version'])
        with closing(self.store.connect()) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM backups').fetchone()[0], 0)
            self.assertIsNone(db.execute('SELECT key FROM requests WHERE key=?', (key,)).fetchone())

    def test_goal_effort_fill_and_half_hour_validation(self):
        response=self.action('save',dict(title='N1',kind='goal',important='yes',target_hours='10'))
        ident=response.get_json()['state']['tasks'][0]['id']
        self.assertEqual(self.action('progress',dict(id=ident,session_start='09:00',actual='0.25')).status_code,400)
        self.assertEqual(self.action('progress',dict(id=ident,session_start='09:00',actual='0.5')).status_code,200)
        self.assertEqual(self.state()['view']['progress'][ident],[30,600,0.05])

    def test_fixed_event_cannot_move_and_cancel_only_one(self):
        response=self.action('save_event',dict(title='Class',category='fixed',date='2026-11-12',event_start='10:00',event_end='12:00',repeat='daily'))
        ident=response.get_json()['state']['events'][0]['id']
        self.assertEqual(self.action('move_event',dict(id=ident,occurrence_date='2026-11-12',new_date='2026-11-12',new_start='13:00')).status_code,400)
        self.assertEqual(self.action('cancel_occurrence',dict(id=ident,occurrence_date='2026-11-12')).status_code,200)
        occurrences=self.state()['view']['occurrences']
        self.assertEqual(len(occurrences),6)
        self.assertFalse(any(block['date']=='2026-11-12' for block in occurrences))

    def test_manual_task_move_keeps_length_and_persists(self):
        ident=self.task(); block=self.state()['state']['calendar'][0]
        response=self.action('move_block',dict(id=ident,source_date=block['date'],source_start='09:00',source_end='11:00',new_date=block['date'],new_start='12:00'))
        self.assertEqual(response.status_code,200,response.get_json())
        self.assertEqual(self.state()['state']['calendar'][0]['start'],720)
        # A fresh app instance sees the same committed data.
        other=create_app(dict(self.config,DATABASE=self.store.path)).test_client();self.login(other)
        self.assertEqual(self.state(other)['state']['calendar'][0]['start'],720)

    def test_suggestion_never_blocks_original_progress(self):
        first=self.task('First'); second=self.task('Second')
        response=self.action('progress',dict(id=first,session_start='09:00',actual='0.5',finished='yes'))
        self.assertEqual(response.status_code,200)
        self.assertIsNotNone(self.state()['state']['proposal'])
        response=self.action('progress',dict(id=second,session_start='11:00',actual='0.5'))
        self.assertEqual(response.status_code,200,response.get_json())

    def test_password_change_revokes_all_devices(self):
        device=self.app.test_client();self.login(device)
        current=self.state()
        response=self.client.post('/api/password',json=dict(current='correct-password-alice',password='replacement-password'),headers={'X-CSRF-Token':current['csrf'],'X-Planwise-Client':'1'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(device.get('/api/state').status_code,401)
        self.assertEqual(self.client.get('/api/state').status_code,401)

    def test_admin_can_create_empty_account_but_member_cannot(self):
        current=self.state()
        response=self.client.post('/api/users',json=dict(username='charlie',password='correct-password-charlie'),headers={'X-CSRF-Token':current['csrf'],'X-Planwise-Client':'1'})
        self.assertEqual(response.status_code,201)
        bob=self.app.test_client();self.login(bob,'bob');current=self.state(bob)
        response=bob.post('/api/users',json=dict(username='david',password='correct-password-david'),headers={'X-CSRF-Token':current['csrf'],'X-Planwise-Client':'1'})
        self.assertEqual(response.status_code,403)

    def test_throttle_persists_across_failed_login_transactions(self):
        client=self.app.test_client()
        for i in range(8):
            response=client.post('/api/login',json=dict(username='alice',password='bad'),headers={'X-Planwise-Client':'1'})
            self.assertEqual(response.status_code,401)
        self.assertEqual(self.login(client).status_code,429)

    def test_offline_attachment_contains_no_csrf_or_executable_user_html(self):
        self.task('</script><script>alert(1)</script>')
        current=self.state();response=self.client.get('/api/offline');html=response.get_data(as_text=True)
        self.assertEqual(response.status_code,200)
        self.assertNotIn(current['csrf'],html)
        self.assertNotIn('</script><script>alert(1)</script>',html)
        self.assertIn('id="offline-data"',html)
        self.assertIn("form-action 'none'",response.headers['Content-Security-Policy'])
        self.assertNotIn('password_hash',html)

    def test_hong_kong_time_is_independent_of_client_timezone(self):
        current=self.state()
        self.assertEqual(current['view']['today'],'2026-11-12')
        self.assertEqual(current['view']['cutoff'],540)

    def test_settings_and_legacy_availability_can_be_used_on_nas(self):
        response=self.action('save_settings',dict(language='zh-Hans',workdays=[1,3,5]))
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.get_json()['state']['workdays'],[1,3,5])
        self.assertEqual(response.get_json()['state']['language'],'zh-Hans')
        self.assertEqual(self.action('windows',{}).status_code,200)
        self.assertEqual(self.state()['state']['time_model'],'custom')
        self.assertEqual(self.action('full_day').status_code,200)
        self.assertEqual(self.state()['state']['time_model'],'free')


    def assert_invalid_unchanged(self, action, fields):
        before = self.state()
        response = self.action(action, fields)
        self.assertEqual(response.status_code, 400, response.get_data(as_text=True))
        self.assertEqual(response.get_json()['code'], 'invalid')
        after = self.state()
        self.assertEqual(after['state'], before['state'])
        self.assertEqual(after['version'], before['version'])
        return response.get_json()['error']

    def test_scalar_empty_and_multiple_values_are_rejected_without_changes(self):
        for action, fields in [('save', {'title': []}), ('save_settings', {'language': []}),
                               ('save', {'title': ['one', 'two']}), ('import_data', {'backup_json': []}),
                               ('save_event', {'title': []}), ('move_block', {'id': []})]:
            with self.subTest(action=action, fields=fields):
                self.assert_invalid_unchanged(action, fields)

    def test_nested_boolean_null_and_nonfinite_fields_are_rejected(self):
        for value in [None, True, {}, [None], float('nan'), float('inf')]:
            with self.subTest(value=value):
                self.assert_invalid_unchanged('save', {'title': value})

    def test_empty_workdays_and_multiple_weekdays_remain_supported(self):
        response = self.action('save_settings', {'language': 'en', 'workdays': []})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['state']['workdays'], [])
        response = self.action('save_event', dict(title='Weekly', category='private', repeat='weekly',
            date='2026-11-12', event_start='09:00', event_end='09:30', weekdays=[1, 3, 5]))
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()['state']['events'][-1]['weekdays'], [1, 3, 5])

    def test_invalid_dates_have_friendly_localized_errors(self):
        base = dict(title='Essay', course='', kind='deadline', due='2026-02-30', hours='1', important='yes')
        for language in ['zh-Hant', 'zh-Hans', 'en']:
            self.assertEqual(self.action('save_settings', {'language': language, 'workdays': []}).status_code, 200)
            message = self.assert_invalid_unchanged('save', base)
            self.assertNotIn('must be in range', message)
            self.assertIn('2026-11-14', message)
            self.assertIn({'zh-Hant': '日期無效', 'zh-Hans': '日期无效', 'en': 'Invalid date'}[language], message)
        self.assert_invalid_unchanged('save', dict(base, due='2026-11-14', start='not-a-date'))
        self.assert_invalid_unchanged('save_event', dict(title='Event', category='private', repeat='none',
            date='2026-02-30', event_start='09:00', event_end='10:00'))

    def test_bad_backup_shapes_use_backup_error_and_preserve_data(self):
        self.task()
        for text in ['{bad json', 'null', '[]', '{"tasks":null}',
                     '{"format":"planwise-backup","backup_version":1}',
                     '{"version":2,"tasks":[],"capacity":{},"events":[{}]}']:
            with self.subTest(text=text):
                message = self.assert_invalid_unchanged('import_data', {'replace_confirm': 'yes', 'backup_json': text})
                self.assertIn('備份檔格式不正確', message)

    def test_invalid_hours_names_and_workdays_leave_plan_unchanged(self):
        base = dict(title='Essay', course='', kind='deadline', due='2026-11-14', hours='1', important='yes')
        for value in ['abc', '-1', '0.25', 'NaN', 'Infinity', '1000.5']:
            self.assert_invalid_unchanged('save', dict(base, hours=value))
        for value in ['', '   ', 'x'*101]:
            self.assert_invalid_unchanged('save', dict(base, title=value))
        for value in [['oops'], [-1], [7]]:
            self.assert_invalid_unchanged('save_settings', {'language': 'en', 'workdays': value})

    def test_unexpected_action_failure_is_json_and_rolls_back(self):
        before = self.state()
        with patch('nas.application.apply', side_effect=RuntimeError('private internal detail')):
            with self.assertLogs(self.app.logger, level='ERROR'):
                response = self.action('save_policy', {})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json()['code'], 'internal')
        self.assertNotIn('private internal detail', response.get_data(as_text=True))
        after = self.state()
        self.assertEqual(after['state'], before['state'])
        self.assertEqual(after['version'], before['version'])

    def test_unknown_api_and_method_return_json_http_errors(self):
        for response, status in [(self.client.get('/api/does-not-exist'), 404),
                                 (self.client.get('/api/actions'), 405)]:
            self.assertEqual(response.status_code, status)
            self.assertEqual(response.get_json()['code'], 'http_error')


if __name__=='__main__':
    unittest.main()
