"""Verify first account creation through the coursework launcher and NAS isolation."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from flask import Flask

import main as launcher
from nas.application import create_app


HEADERS = {"X-Planwise-Client": "1"}
CREDENTIALS = {"username": "first-user", "password": "Temporary-test-password",
               "password_confirm": "Temporary-test-password", "language": "en"}


class LocalSetupTests(unittest.TestCase):
    def setUp(self):
        folder = self.enterContext(tempfile.TemporaryDirectory())
        self.database = Path(folder) / "test.sqlite3"
        with patch.object(launcher, "DEMO_DATABASE", self.database), patch("sys.argv", ["main.py"]):
            with patch.object(Flask, "run", autospec=True) as run:
                launcher.main()
        self.assertEqual(run.call_args.kwargs["host"], "127.0.0.1")
        self.app = run.call_args.args[0]

    def test_first_run_creates_admin_and_signs_in_once(self):
        client = self.app.test_client()
        state = client.get("/api/state")
        self.assertEqual((state.status_code, state.json["code"]), (401, "setup_required"))
        bad = client.post("/api/setup", json=dict(CREDENTIALS, password_confirm="mismatch"), headers=HEADERS)
        self.assertEqual((bad.status_code, bad.json["code"]), (400, "password_mismatch"))
        result = client.post("/api/setup", json=CREDENTIALS, headers=HEADERS)
        self.assertEqual(result.status_code, 201, result.json)
        self.assertIn("HttpOnly", result.headers["Set-Cookie"])
        current = client.get("/api/state").json
        self.assertEqual(current["user"]["username"], CREDENTIALS["username"])
        self.assertTrue(current["user"]["is_admin"])
        self.assertEqual(current["state"]["language"], "en")
        fresh = self.app.test_client()
        self.assertEqual(fresh.get("/api/state").json["code"], "unauthorized")
        repeat = fresh.post("/api/setup", json=CREDENTIALS, headers=HEADERS)
        self.assertEqual((repeat.status_code, repeat.json["code"]), (409, "setup_complete"))

    def test_first_setup_only_available_to_local_demo(self):
        client = self.app.test_client()
        public_address = {"REMOTE_ADDR": "192.0.2.5"}
        result = client.post("/api/setup", json=CREDENTIALS, headers=HEADERS, environ_overrides=public_address)
        self.assertEqual(result.status_code, 404)
        wrong_host = client.post("/api/setup", json=CREDENTIALS, headers=HEADERS, base_url="http://other.example")
        self.assertEqual(wrong_host.status_code, 400)
        cross_site = client.post("/api/setup", json=CREDENTIALS,
                                 headers=dict(HEADERS, Origin="https://other.example"))
        self.assertEqual(cross_site.status_code, 403)

        nas = create_app({"DATABASE": str(self.database.with_name("nas.sqlite3"))}).test_client()
        self.assertEqual(nas.get("/api/state").json["code"], "unauthorized")
        self.assertEqual(nas.post("/api/setup", json=CREDENTIALS, headers=HEADERS).status_code, 404)
        self.assertEqual(nas.post("/api/register", json=CREDENTIALS, headers=HEADERS).json["code"],
                         "invalid_invitation")

    def test_two_simultaneous_setups_can_create_only_one_account(self):
        def register(username):
            return self.app.test_client().post(
                "/api/setup", json=dict(CREDENTIALS, username=username), headers=HEADERS
            ).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(register, ["one", "two"])), [201, 409])
