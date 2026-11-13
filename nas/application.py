"""Same-origin JSON API, served independently from the static frontend."""
from datetime import datetime, timedelta, timezone
from contextlib import closing
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import time
from urllib.parse import urlsplit

from flask import Flask, g, jsonify, request, send_from_directory
from werkzeug.security import check_password_hash, generate_password_hash
from i18n import translate
from storage import export_state
from timetable import initialize
from nas.database import Database, digest, password_valid
from nas.domain import apply, view
from nas.proxy import tunnel_proxy

HKT = timezone(timedelta(hours=8))
COOKIE = 'planwise_session'


class APIError(Exception):
    def __init__(self, message, status=400, code='invalid'):
        self.message, self.status, self.code = message, status, code


def create_app(config=None):
    app = Flask(__name__, static_folder='static', static_url_path='/static')
    app.config.update(DATABASE=os.environ.get('PLANWISE_DATABASE', '/data/planwise.sqlite3'),
                      COOKIE_SECURE=os.environ.get('PLANWISE_COOKIE_SECURE') == '1',
                      PUBLIC_ORIGIN=os.environ.get('PLANWISE_PUBLIC_ORIGIN',''),
                      TRUSTED_PROXY_IPS=os.environ.get('PLANWISE_TRUSTED_PROXY_IPS',''),
                      MAX_CONTENT_LENGTH=8_000_000, NOW=lambda: datetime.now(HKT))
    if config:
        app.config.update(config)
    app.wsgi_app = tunnel_proxy(app.wsgi_app,app.config['PUBLIC_ORIGIN'],app.config['TRUSTED_PROXY_IPS'],app.config['COOKIE_SECURE'])
    store = Database(app.config['DATABASE'])
    app.extensions['store'] = store
    # Equal-cost password verification for unknown accounts.
    dummy_hash = generate_password_hash(secrets.token_urlsafe(32), method='scrypt')

    def clock():
        now = app.config['NOW']()
        return now.date(), (now.hour*60+now.minute)//30*30

    def body():
        value = request.get_json(silent=True)
        if not isinstance(value, dict):
            raise APIError('JSON object required.')
        return value

    def find_session(db):
        token = request.cookies.get(COOKIE, '')
        return db.execute('''SELECT s.*, u.username, u.is_admin FROM sessions s
            JOIN users u ON u.id=s.user_id WHERE token_hash=? AND expires>?''', (digest(token), int(time.time()))).fetchone()

    def authorize(db):
        session = find_session(db)
        if session is None:
            raise APIError('Please sign in again.', 401, 'unauthorized')
        if request.method != 'GET' and not secrets.compare_digest(request.headers.get('X-CSRF-Token', ''), session['csrf']):
            raise APIError('Session check failed. Reload before saving.', 403, 'csrf')
        g.language = 'zh-Hant'
        return session

    def signed_in(token, status=200):
        response = jsonify(ok=True)
        response.status_code = status
        response.set_cookie(COOKIE,token,max_age=7*86400,httponly=True,secure=app.config['COOKIE_SECURE'],samesite='Strict',path='/')
        return response

    def snapshot(db, session):
        row = db.execute('SELECT * FROM plans WHERE user_id=?', (session['user_id'],)).fetchone()
        state = json.loads(row['data'])
        before = json.dumps(state, sort_keys=True)
        today, cutoff = clock()
        initialize(state, today, cutoff)
        version, saved_at = row['version'], row['saved_at']
        if json.dumps(state, sort_keys=True) != before:
            version += 1
            saved_at = int(time.time())
            db.execute('UPDATE plans SET data=?,version=?,saved_at=? WHERE user_id=?', (json.dumps(state), version, saved_at, session['user_id']))
        g.language = state['language']
        result = dict(api_version=1, user=dict(id=session['user_id'], username=session['username'], is_admin=bool(session['is_admin'])),
                      csrf=session['csrf'], version=version, saved_at=saved_at, state=state, view=view(state,today,cutoff))
        if session['is_admin']:
            result['invitations'] = store.invitations(db)
        return result

    @app.before_request
    def same_origin():
        if request.path.startswith('/api/') and request.method != 'GET':
            origin = request.headers.get('Origin')
            referer = request.headers.get('Referer')
            expected = urlsplit(request.host_url)
            for supplied in (origin, referer):
                if supplied:
                    try:
                        parsed = urlsplit(supplied)
                    except ValueError:
                        raise APIError('Cross-origin request refused.', 403, 'origin') from None
                    if parsed.scheme != expected.scheme or parsed.netloc != expected.netloc:
                        raise APIError('Cross-origin request refused.', 403, 'origin')
            if request.headers.get('Sec-Fetch-Site') == 'cross-site' or request.headers.get('X-Planwise-Client') != '1':
                raise APIError('Same-origin client required.', 403, 'origin')

    @app.after_request
    def headers(response):
        response.headers['Cache-Control'] = 'private, no-store' if request.path.startswith('/api/') else 'no-cache'
        if request.path.startswith('/api/'):
            response.headers['Cloudflare-CDN-Cache-Control'] = 'no-store'
            response.headers['CDN-Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['X-Frame-Options'] = 'DENY'
        if 'Content-Security-Policy' not in response.headers:
            response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        return response

    @app.errorhandler(APIError)
    def api_error(exc):
        return jsonify(error=translate(exc.message, getattr(g,'language','zh-Hant')), code=exc.code), exc.status

    @app.errorhandler(413)
    def too_large(exc):
        return jsonify(error='Backup/request exceeds 8 MB.', code='too_large'), 413

    @app.errorhandler(sqlite3.Error)
    def database_error(exc):
        app.logger.error('Database operation failed: %s', type(exc).__name__)
        return jsonify(error='Storage unavailable; changes were not saved.', code='storage'), 503

    @app.get('/')
    def index():
        return app.send_static_file('index.html')

    @app.get('/sw.js')
    def service_worker():
        return send_from_directory(app.static_folder, 'sw.js')

    @app.get('/healthz')
    def health():
        with closing(store.connect()) as db:
            db.execute('SELECT 1 FROM users LIMIT 1').fetchone()
        return jsonify(ok=True, edition='nas', api_version=1, version='0.3.0')

    @app.post('/api/login')
    def login():
        data = body()
        username, password = data.get('username',''), data.get('password','')
        if not isinstance(username,str) or not isinstance(password,str) or len(username)>40 or len(password)>200:
            raise APIError('Invalid username or password.', 401)
        now = int(time.time())
        keys = ['ip:'+str(request.remote_addr), 'user:'+username.lower()]
        with store.transaction() as db:
            db.execute('DELETE FROM attempts WHERE at < ?', (now-900,))
            if any(db.execute('SELECT count(*) FROM attempts WHERE key=?', (key,)).fetchone()[0] >= (30 if key.startswith('ip:') else 8) for key in keys):
                raise APIError('Too many attempts. Try again in 15 minutes.', 429, 'rate_limited')
            user = db.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
            valid = check_password_hash(user['password_hash'] if user else dummy_hash, password)
            if not valid or user is None:
                db.executemany('INSERT INTO attempts VALUES(?,?)', [(key,now) for key in keys])
                # Return after committing the failed-attempt counters.
                denied = True
            else:
                denied = False
                db.execute('DELETE FROM attempts WHERE key=?', (keys[1],))
                old = request.cookies.get(COOKIE,'')
                db.execute('DELETE FROM sessions WHERE token_hash=?', (digest(old),))
                token, csrf = store.session(db,user['id'])
        if denied:
            raise APIError('Invalid username or password.', 401, 'credentials')
        return signed_in(token)

    @app.post('/api/register')
    def register():
        data = body()
        code, username, password = data.get('invite_code'), data.get('username'), data.get('password')
        if not isinstance(code,str) or not 16 <= len(code.strip()) <= 80:
            raise APIError('Invalid, expired or already used invitation code.',400,'invalid_invitation')
        if not isinstance(username,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{3,40}',username):
            raise APIError('Username: 3–40 letters, digits, dots, underscores or hyphens.',400,'invalid_username')
        try:
            password_valid(password)
        except ValueError as exc:
            raise APIError(str(exc),400,'password_length') from None
        if data.get('password_confirm') != password:
            raise APIError('Passwords do not match.',400,'password_mismatch')
        language = data.get('language','zh-Hant')
        if language not in ('zh-Hant','zh-Hans','en'):
            raise APIError('Invalid language.')
        now = int(time.time())
        attempt_key = 'register-ip:'+str(request.remote_addr)
        error = None
        with store.transaction() as db:
            if find_session(db):
                raise APIError('Sign out before creating another account.',409,'already_signed_in')
            db.execute('DELETE FROM attempts WHERE at < ?', (now-900,))
            if db.execute('SELECT count(*) FROM attempts WHERE key=?',(attempt_key,)).fetchone()[0] >= 12:
                raise APIError('Too many attempts. Try again in 15 minutes.',429,'rate_limited')
            invitation = db.execute('SELECT * FROM invitations WHERE code_hash=?',(digest(code.strip()),)).fetchone()
            if invitation is None or invitation['used_by'] is not None or invitation['revoked_at'] is not None or invitation['expires_at'] <= now:
                error = APIError('Invalid, expired or already used invitation code.',400,'invalid_invitation')
            else:
                try:
                    user_id = store.create_user(username,password,False,db,language=language)
                except ValueError as exc:
                    error = APIError(str(exc),400,'username_taken')
                else:
                    db.execute('UPDATE invitations SET used_by=?,used_at=? WHERE id=?',(user_id,now,invitation['id']))
                    token, _ = store.session(db,user_id)
                    db.execute('DELETE FROM attempts WHERE key=?',(attempt_key,))
            if error:
                # Commit failed-attempt counters without consuming an invitation or creating a user.
                db.execute('INSERT INTO attempts VALUES(?,?)',(attempt_key,now))
        if error:
            raise error
        return signed_in(token,201)

    @app.get('/api/invitations')
    @app.post('/api/invitations')
    def invitations():
        with store.transaction() as db:
            session = authorize(db)
            if not session['is_admin']:
                raise APIError('Administrator account required.',403,'forbidden')
            result = {}
            if request.method == 'POST':
                data = body()
                if data.get('action') == 'create':
                    code = secrets.token_urlsafe(24)
                    now = int(time.time())
                    db.execute('INSERT INTO invitations(code_hash,created_by,created_at,expires_at) VALUES(?,?,?,?)',
                               (digest(code),session['user_id'],now,now+7*86400))
                    result['code'] = code
                elif data.get('action') == 'revoke' and type(data.get('id')) is int:
                    changed = db.execute('UPDATE invitations SET revoked_at=? WHERE id=? AND used_by IS NULL AND revoked_at IS NULL',
                                         (int(time.time()),data['id'])).rowcount
                    if not changed:
                        raise APIError('Invitation was already used or revoked.',409,'invitation_unavailable')
                else:
                    raise APIError('Unknown invitation action.')
            result['invitations'] = store.invitations(db)
        return jsonify(result)

    @app.get('/api/state')
    def get_state():
        with store.transaction() as db:
            return jsonify(snapshot(db,authorize(db)))

    @app.post('/api/actions')
    def action():
        data = body()
        if type(data.get('version')) is not int or not isinstance(data.get('action'),str) or not re.fullmatch(r'[A-Za-z0-9-]{16,80}',str(data.get('request_id',''))):
            raise APIError('Version, action and unique request_id are required.')
        fingerprint = digest(json.dumps(data,sort_keys=True,ensure_ascii=True))
        with store.transaction() as db:
            session = authorize(db)
            current = snapshot(db,session)
            prior = db.execute('SELECT fingerprint FROM requests WHERE user_id=? AND key=?', (session['user_id'],data['request_id'])).fetchone()
            if prior:
                if prior['fingerprint'] != fingerprint:
                    raise APIError('Request ID was reused for a different change.',409,'request_reused')
                return jsonify(**current,replayed=True)
            if data['version'] != current['version']:
                raise APIError('Another device updated this plan. Refresh and review your change before saving again.',409,'conflict')
            today,cutoff = clock()
            try:
                updated = apply(current['state'],data['action'],data.get('fields',{}),today,cutoff)
                serialized = json.dumps(updated,ensure_ascii=False)
                if len(serialized.encode()) > 4_000_000:
                    raise ValueError('Plan exceeds 4 MB. Export and archive old records.')
            except (ValueError,TypeError,KeyError,OverflowError,RecursionError) as exc:
                raise APIError(str(exc) if isinstance(exc,ValueError) else 'Invalid data; your plan was not changed.') from None
            if data['action']=='import_data':
                db.execute('INSERT INTO backups(user_id,version,data,at) VALUES(?,?,?,?)',(session['user_id'],current['version'],json.dumps(current['state']),int(time.time())))
                db.execute('DELETE FROM backups WHERE user_id=? AND id NOT IN (SELECT id FROM backups WHERE user_id=? ORDER BY id DESC LIMIT 10)',(session['user_id'],session['user_id']))
            db.execute('UPDATE plans SET data=?,version=version+1,saved_at=? WHERE user_id=?',(serialized,int(time.time()),session['user_id']))
            db.execute('INSERT INTO requests VALUES(?,?,?,?)',(session['user_id'],data['request_id'],fingerprint,int(time.time())))
            db.execute('DELETE FROM requests WHERE user_id=? AND key NOT IN (SELECT key FROM requests WHERE user_id=? ORDER BY at DESC,rowid DESC LIMIT 200)',(session['user_id'],session['user_id']))
            return jsonify(snapshot(db,session))

    @app.get('/api/export')
    def export():
        with store.transaction() as db:
            current = snapshot(db,authorize(db))
        return app.response_class(export_state(current['state']),mimetype='application/json',headers={'Content-Disposition':'attachment; filename="planwise-backup.json"'})

    @app.post('/api/logout')
    def logout():
        with store.transaction() as db:
            session = authorize(db)
            db.execute('DELETE FROM sessions WHERE token_hash=?',(session['token_hash'],))
        response = jsonify(ok=True)
        response.delete_cookie(COOKIE,path='/')
        return response

    @app.get('/api/offline')
    def offline_snapshot():
        with store.transaction() as db:
            current = snapshot(db,authorize(db))
        del current['csrf']
        current.pop('invitations',None)
        root = Path(app.static_folder)
        html = (root/'index.html').read_text(encoding='utf-8')
        css = (root/'ui.css').read_text(encoding='utf-8')
        js = (root/'ui.js').read_text(encoding='utf-8')
        payload = json.dumps(current,ensure_ascii=True).replace('<','\\u003c')
        html = html.replace('<link rel="stylesheet" href="/static/ui.css">', '<style>'+css+'</style>')
        html = html.replace('<script src="/static/ui.js" defer></script>', '')
        html = html.replace('</body>', '<script type="application/json" id="offline-data">'+payload+'</script><script>'+js+'</script></body>')
        response = app.response_class(html,mimetype='text/html',headers={'Content-Disposition':'attachment; filename="planwise-readonly.html"'})
        # An attachment opened as a file has no server headers; also allow inline assets when previewed.
        response.headers['Content-Security-Policy'] = "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'"
        return response

    @app.post('/api/password')
    def password():
        data = body()
        try:
            password_valid(data.get('password'))
        except ValueError as exc:
            raise APIError(str(exc)) from None
        if not isinstance(data.get('current'),str) or len(data['current'])>200:
            raise APIError('Current password is required.')
        with store.transaction() as db:
            session = authorize(db)
            user = db.execute('SELECT * FROM users WHERE id=?',(session['user_id'],)).fetchone()
            if not check_password_hash(user['password_hash'],data['current']):
                raise APIError('Current password is incorrect.',403)
            db.execute('UPDATE users SET password_hash=? WHERE id=?',(generate_password_hash(data['password'],method='scrypt'),session['user_id']))
            db.execute('DELETE FROM sessions WHERE user_id=?',(session['user_id'],))
        response = jsonify(ok=True)
        response.delete_cookie(COOKIE,path='/')
        return response

    @app.post('/api/users')
    def users():
        data = body()
        with store.transaction() as db:
            session = authorize(db)
            if not session['is_admin']:
                raise APIError('Administrator account required.',403,'forbidden')
            try:
                ident = store.create_user(data.get('username'),data.get('password'),False,db)
            except ValueError as exc:
                raise APIError(str(exc)) from None
        return jsonify(id=ident),201

    return app
