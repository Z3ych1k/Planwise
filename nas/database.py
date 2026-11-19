"""SQLite transactions keep account ownership and version checks together."""
from contextlib import closing, contextmanager
import hashlib
import json
from pathlib import Path
import re
import secrets
import sqlite3
import time

from werkzeug.security import generate_password_hash
from storage import empty_state


def password_valid(password):
    if not isinstance(password, str) or not 12 <= len(password) <= 200:
        raise ValueError('Password must contain 12–200 characters.')


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class Database:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY, username TEXT UNIQUE COLLATE NOCASE NOT NULL,
                    password_hash TEXT NOT NULL, is_admin INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS plans (
                    user_id INTEGER PRIMARY KEY REFERENCES users(id),
                    version INTEGER NOT NULL, data TEXT NOT NULL, saved_at INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
                    csrf TEXT NOT NULL, expires INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS attempts (key TEXT NOT NULL, at INTEGER NOT NULL);
                CREATE INDEX IF NOT EXISTS attempts_key ON attempts(key, at);
                CREATE TABLE IF NOT EXISTS requests (
                    user_id INTEGER NOT NULL, key TEXT NOT NULL, fingerprint TEXT NOT NULL,
                    at INTEGER NOT NULL, PRIMARY KEY(user_id, key));
                CREATE TABLE IF NOT EXISTS backups (
                    id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL,
                    version INTEGER NOT NULL, data TEXT NOT NULL, at INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS invitations (
                    id INTEGER PRIMARY KEY, code_hash TEXT UNIQUE NOT NULL,
                    created_by INTEGER NOT NULL REFERENCES users(id),
                    created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL,
                    used_by INTEGER REFERENCES users(id), used_at INTEGER,
                    revoked_at INTEGER);
            ''')

    def connect(self):
        db = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA busy_timeout=15000')
        return db

    @contextmanager
    def transaction(self):
        db = self.connect()
        try:
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def plan(self, db, user_id):
        return db.execute('SELECT * FROM plans WHERE user_id=?', (user_id,)).fetchone()

    def save_initialized_plan(self, db, user_id, state, version, saved_at):
        db.execute('UPDATE plans SET data=?,version=?,saved_at=? WHERE user_id=?',
                   (json.dumps(state), version, saved_at, user_id))

    def request_fingerprint(self, db, user_id, key):
        return db.execute('SELECT fingerprint FROM requests WHERE user_id=? AND key=?',
                          (user_id, key)).fetchone()

    def backup_before_import(self, db, user_id, version, state):
        db.execute('INSERT INTO backups(user_id,version,data,at) VALUES(?,?,?,?)',
                   (user_id, version, json.dumps(state), int(time.time())))
        db.execute('DELETE FROM backups WHERE user_id=? AND id NOT IN (SELECT id FROM backups WHERE user_id=? ORDER BY id DESC LIMIT 10)',
                   (user_id, user_id))

    def save_plan_action(self, db, user_id, serialized, key, fingerprint):
        db.execute('UPDATE plans SET data=?,version=version+1,saved_at=? WHERE user_id=?',
                   (serialized, int(time.time()), user_id))
        db.execute('INSERT INTO requests VALUES(?,?,?,?)',
                   (user_id, key, fingerprint, int(time.time())))
        db.execute('DELETE FROM requests WHERE user_id=? AND key NOT IN (SELECT key FROM requests WHERE user_id=? ORDER BY at DESC,rowid DESC LIMIT 200)',
                   (user_id, user_id))

    def has_users(self, db):
        return db.execute('SELECT 1 FROM users LIMIT 1').fetchone() is not None

    def create_user(self, username, password, admin=False, db=None, language='zh-Hant'):
        if not isinstance(username, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{3,40}', username):
            raise ValueError('Username: 3–40 letters, digits, dots, underscores or hyphens.')
        password_valid(password)
        if language not in ('zh-Hant','zh-Hans','en'):
            raise ValueError('Invalid language.')
        hashed = generate_password_hash(password, method='scrypt')
        def insert(connection):
            try:
                cursor = connection.execute('INSERT INTO users(username,password_hash,is_admin) VALUES(?,?,?)', (username, hashed, int(admin)))
            except sqlite3.IntegrityError:
                raise ValueError('Username already exists.') from None
            state = empty_state()
            state['language'] = language
            connection.execute('INSERT INTO plans VALUES(?,?,?,?)', (cursor.lastrowid, 1, json.dumps(state), int(time.time())))
            return cursor.lastrowid
        if db is not None:
            return insert(db)
        with self.transaction() as connection:
            return insert(connection)

    def session(self, db, user_id):
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        now = int(time.time())
        db.execute('DELETE FROM sessions WHERE expires < ?', (now,))
        db.execute('INSERT INTO sessions VALUES(?,?,?,?)', (digest(token), user_id, csrf, now + 7*86400))
        return token, csrf

    def invitations(self, db):
        """Return administrator metadata, never usable invitation secrets."""
        now = int(time.time())
        result = []
        for row in db.execute('''SELECT i.id,i.created_at,i.expires_at,i.revoked_at,
                i.used_at,u.username AS used_by FROM invitations i
                LEFT JOIN users u ON u.id=i.used_by ORDER BY i.id DESC LIMIT 50'''):
            item = dict(row)
            item['status'] = 'used' if item['used_at'] is not None else 'revoked' if item['revoked_at'] is not None else 'expired' if item['expires_at'] <= now else 'pending'
            result.append(item)
        return result

    def backup_to(self, path):
        target = Path(path)
        if target.exists():
            raise ValueError('Backup destination already exists; choose a new filename.')
        with closing(self.connect()) as source, closing(sqlite3.connect(target)) as destination:
            source.backup(destination)
