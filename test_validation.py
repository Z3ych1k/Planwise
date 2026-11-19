"""Input boundary regression tests using temporary data and loopback HTTP only."""
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
    def test_scalar_and_numeric_values_keep_existing_form_contract(self):
        self.assertEqual(normalize_fields({'title': 'x', 'hours': 0.5, 'workdays': []}),
                         {'title': ['x'], 'hours': ['0.5'], 'workdays': []})

    def test_structural_limits_and_unsupported_values(self):
        for fields in [None, [], {'title': []}, {'title': ['a', 'b']},
                       {'title': True}, {'title': None}, {'hours': float('nan')},
                       {'hours': float('inf')}, {'weekdays': list(range(21))},
                       {str(i): 'x' for i in range(101)}, {1: 'x'}]:
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                normalize_fields(fields)

    def test_valid_and_invalid_dates(self):
        self.assertEqual(parse_date('2028-02-29'), date(2028, 2, 29))
        for value in ['', '2026-02-30', '2026-13-01', 'text', None, []]:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, '日期無效'):
                parse_date(value)

    def test_deeply_nested_local_file_is_preserved_and_opens_read_only(self):
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
        root = Path(__file__).parent
        self.assertIn('!validation.py', (root/'.dockerignore').read_text())
        self.assertIn('validation.py', (root/'nas/Dockerfile').read_text())
        self.assertIn('validation.py', (root/'android/build-apk.sh').read_text())


class AndroidInputTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name)/'plan.json'
        save_state(self.path, empty_state())
        self.server = make_server(self.path)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.directory.cleanup()

    def post(self, pairs):
        connection = HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        try:
            connection.request('POST', '/', urlencode([('token', TOKEN)]+pairs),
                               {'Content-Type': 'application/x-www-form-urlencoded', 'Accept': 'application/json'})
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def test_duplicate_scalar_is_rejected_and_file_unchanged(self):
        before = self.path.read_bytes()
        status, body = self.post([('action', 'save'), ('title', 'first'), ('title', 'second')])
        self.assertEqual(status, 400)
        self.assertFalse(body['ok'])
        self.assertEqual(self.path.read_bytes(), before)

    def test_bad_date_then_valid_save_and_reload(self):
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


if __name__ == '__main__':
    unittest.main()
