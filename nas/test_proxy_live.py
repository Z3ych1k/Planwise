"""Real TCP/TLS + Gunicorn integration, with isolated cookies and a temporary DB.

The local HTTPS relay emulates Cloudflare's header contract, not its network.
No Cloudflare account, token, public listener or existing NAS is used.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from http.cookiejar import CookieJar
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import http.client
import json
import os
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import uuid

from nas.database import Database

ROOT = Path(__file__).resolve().parents[1]
PASSWORD = 'Member-test-password'


class BrowserSession:
    def __init__(self,origin,context,visitor='198.51.100.20'):
        self.origin,self.visitor=origin,visitor
        self.cookies=CookieJar()
        self.client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies),urllib.request.HTTPSHandler(context=context))

    def call(self,path,fields=None,headers=None):
        base={'X-Planwise-Client':'1','Content-Type':'application/json','Origin':self.origin,'X-Test-Visitor':self.visitor}
        base.update(headers or {})
        request=urllib.request.Request(self.origin+path,data=json.dumps(fields).encode() if fields is not None else None,headers=base)
        try:
            response=self.client.open(request,timeout=10)
        except urllib.error.HTTPError as error:
            response=error
        with response:
            content=response.read().decode()
            return response.status,response.headers,json.loads(content) if 'application/json' in response.headers.get('Content-Type','') else content


class LiveProxyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder=tempfile.TemporaryDirectory(prefix='planwise-https-integration-')
        cls.addClassCleanup(cls.folder.cleanup)
        directory=Path(cls.folder.name)
        cert,key=directory/'test-cert.pem',directory/'test-key.pem'
        config=directory/'cert.cnf'
        config.write_text('[req]\ndistinguished_name=dn\nx509_extensions=ext\nprompt=no\n[dn]\nCN=localhost\n[ext]\nsubjectAltName=DNS:localhost,IP:127.0.0.1\nbasicConstraints=critical,CA:TRUE\nkeyUsage=digitalSignature,keyEncipherment,keyCertSign\n')
        subprocess.run(['openssl','req','-x509','-nodes','-newkey','rsa:2048','-days','1','-config',str(config),'-keyout',str(key),'-out',str(cert)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        cls.context=ssl.create_default_context(cafile=str(cert))
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',0));cls.backend_port=listener.getsockname()[1]

        class Relay(BaseHTTPRequestHandler):
            def relay(self):
                headers={name:value for name,value in self.headers.items() if name.lower() not in ('connection','content-length','transfer-encoding','cf-connecting-ip','x-forwarded-proto') and not name.lower().startswith('x-test-')}
                headers['CF-Connecting-IP']=self.headers.get('X-Test-Visitor','198.51.100.20')
                headers['X-Forwarded-Proto']=self.headers.get('X-Test-Proto','https')
                connection=http.client.HTTPConnection('127.0.0.1',cls.backend_port,timeout=10)
                try:
                    body=self.rfile.read(int(self.headers.get('Content-Length','0')))
                    connection.request(self.command,self.path,body=body,headers=headers)
                    response=connection.getresponse();content=response.read()
                    self.send_response(response.status)
                    for name,value in response.getheaders():
                        if name.lower() not in ('connection','transfer-encoding','content-length','server','date'):
                            self.send_header(name,value)
                    self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content)
                finally:
                    connection.close()
            do_GET=do_POST=relay
            def log_message(self,*args):
                pass

        cls.relay=ThreadingHTTPServer(('127.0.0.1',0),Relay)
        cls.addClassCleanup(cls.relay.server_close)
        cls.origin='https://localhost:'+str(cls.relay.server_port)
        tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.load_cert_chain(cert,key)
        cls.relay.socket=tls.wrap_socket(cls.relay.socket,server_side=True)
        cls.thread=threading.Thread(target=cls.relay.serve_forever,daemon=True);cls.thread.start()
        cls.addClassCleanup(cls.relay.shutdown)
        cls.database=directory/'isolated.sqlite3'
        Database(cls.database).create_user('owner','Owner-test-password',True)
        log=(directory/'gunicorn.log').open('w+')
        cls.addClassCleanup(log.close)
        environment=os.environ.copy()
        environment.update(PLANWISE_DATABASE=str(cls.database),PLANWISE_PUBLIC_ORIGIN=cls.origin,PLANWISE_TRUSTED_PROXY_IPS='127.0.0.1',PLANWISE_COOKIE_SECURE='1')
        cls.process=subprocess.Popen([sys.executable,'-m','gunicorn','--preload','--bind','127.0.0.1:'+str(cls.backend_port),'--forwarded-allow-ips=','--workers','2','--threads','2','nas.application:create_app()'],cwd=ROOT,env=environment,stdout=log,stderr=log)
        cls.addClassCleanup(cls.stop_process)
        for _ in range(60):
            try:
                with urllib.request.urlopen('http://127.0.0.1:'+str(cls.backend_port)+'/healthz',timeout=1) as response:
                    if response.status==200:
                        break
            except OSError:
                if cls.process.poll() is not None:
                    log.seek(0);raise RuntimeError(log.read())
                time.sleep(.1)
        else:
            raise RuntimeError('Isolated Gunicorn did not become ready.')

    @classmethod
    def stop_process(cls):
        cls.process.terminate()
        try:
            cls.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            cls.process.kill();cls.process.wait()

    def ok(self,client,path,fields=None,headers=None,status=200):
        result,_,data=client.call(path,fields,headers)
        self.assertEqual(result,status,data)
        return data

    def login(self,client,name,password=PASSWORD):
        return self.ok(client,'/api/login',dict(username=name,password=password))

    def setUp(self):
        self.admin=BrowserSession(self.origin,self.context)
        self.login(self.admin,'owner','Owner-test-password')
        self.a,self.b=self.member(),self.member()

    def member(self):
        state=self.ok(self.admin,'/api/state')
        invite=self.ok(self.admin,'/api/invitations',dict(action='create'),{'X-CSRF-Token':state['csrf']})
        name='user'+uuid.uuid4().hex[:12]
        client=BrowserSession(self.origin,self.context)
        self.ok(client,'/api/register',dict(invite_code=invite['code'],username=name,password=PASSWORD,password_confirm=PASSWORD,is_admin=True),status=201)
        return client

    def change(self,client,title,current=None,**extra):
        current=current or self.ok(client,'/api/state')
        return client.call('/api/actions',dict(action='save',fields=dict(title=title,kind='goal',important='yes',target_hours='10',**extra),version=current['version'],request_id=str(uuid.uuid4())),{'X-CSRF-Token':current['csrf']})

    def test_admin_and_two_users_login_and_edit_concurrently_without_data_leaks(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            replies=list(pool.map(lambda item:self.change(*item),[(self.a,'Only Alice'),(self.b,'Only Bob')]))
        self.assertEqual([reply[0] for reply in replies],[200,200])
        a=self.ok(self.a,'/api/state');b=self.ok(self.b,'/api/state')
        self.assertEqual([task['title'] for task in a['state']['tasks']],['Only Alice'])
        self.assertEqual([task['title'] for task in b['state']['tasks']],['Only Bob'])
        self.assertFalse(a['user']['is_admin']);self.assertFalse(b['user']['is_admin'])
        self.assertEqual(self.ok(self.admin,'/api/state')['state']['tasks'],[])
        foreign={'id':a['state']['tasks'][0]['id'],'user_id':a['user']['id']}
        code,_,_=self.b.call('/api/actions',dict(action='delete',fields=foreign,version=b['version'],request_id=str(uuid.uuid4())),{'X-CSRF-Token':b['csrf']})
        self.assertEqual(code,400)
        exported=self.ok(self.b,'/api/export?user_id='+str(a['user']['id']))
        self.assertEqual([task['title'] for task in exported['data']['tasks']],['Only Bob'])
        self.assertEqual(self.ok(self.b,'/api/state?user_id='+str(a['user']['id']))['user']['id'],b['user']['id'])
        for client in (self.a,self.b):
            state=self.ok(client,'/api/state')
            self.ok(client,'/api/invitations',status=403)
            self.ok(client,'/api/invitations',dict(action='create'),{'X-CSRF-Token':state['csrf']},status=403)

    def test_same_account_second_device_sees_changes_and_stale_save_conflicts(self):
        a=self.ok(self.a,'/api/state');second=BrowserSession(self.origin,self.context)
        self.login(second,a['user']['username'])
        old=self.ok(second,'/api/state')
        self.assertEqual(self.change(self.a,'New desktop task')[0],200)
        self.assertEqual(self.change(second,'Stale phone task',old)[0],409)
        latest=self.ok(second,'/api/state')
        self.assertEqual([task['title'] for task in latest['state']['tasks']],['New desktop task'])

    def test_logout_and_password_change_revoke_only_the_intended_sessions(self):
        first=self.ok(self.a,'/api/state');name=first['user']['username']
        second=BrowserSession(self.origin,self.context);self.login(second,name)
        self.ok(self.a,'/api/logout',{}, {'X-CSRF-Token':first['csrf']})
        self.ok(self.a,'/api/state',status=401)
        current=self.ok(second,'/api/state')
        self.login(self.a,name)
        self.ok(second,'/api/password',dict(current=PASSWORD,password='Replacement-test-password'),{'X-CSRF-Token':current['csrf']})
        self.ok(self.a,'/api/state',status=401);self.ok(second,'/api/state',status=401)
        self.ok(self.b,'/api/state');self.ok(self.admin,'/api/state')
        self.login(second,name,'Replacement-test-password')

    def test_https_cookies_and_all_account_responses_refuse_public_caching(self):
        cookies=list(self.a.cookies)
        self.assertEqual(len(cookies),1);self.assertTrue(cookies[0].secure)
        self.assertTrue(cookies[0].has_nonstandard_attr('HttpOnly'))
        insecure=urllib.request.Request(self.origin.replace('https:','http:')+'/api/state')
        self.a.cookies.add_cookie_header(insecure)
        self.assertIsNone(insecure.get_header('Cookie'))
        for client,path in [(self.a,'/api/state'),(self.a,'/api/export'),(self.a,'/api/offline'),(BrowserSession(self.origin,self.context),'/api/state')]:
            _,headers,_=client.call(path)
            self.assertEqual(headers['Cache-Control'],'private, no-store')
            self.assertEqual(headers['Cloudflare-CDN-Cache-Control'],'no-store')

    def test_bad_origin_and_forwarded_fields_cannot_bypass_auth_or_csrf(self):
        current=self.ok(self.a,'/api/state')
        for origin in ('https://evil.example','http://localhost','null','https://[broken'):
            self.ok(self.a,'/api/invitations',dict(action='create'),{'Origin':origin,'X-CSRF-Token':current['csrf']},status=403)
        self.ok(self.a,'/api/logout',{},status=403)
        self.ok(self.a,'/api/state',headers={'X-Test-Proto':'http'},status=403)
        self.ok(self.a,'/api/state',headers={'X-Test-Visitor':'198.51.100.1, 192.0.2.1'},status=400)
        self.ok(self.a,'/api/state',headers={'Host':'evil.example'},status=400)
        # A real edge overwrites client-supplied protocol/IP fields.
        self.ok(self.a,'/api/state',headers={'X-Forwarded-Proto':'http','CF-Connecting-IP':'bad','X-Forwarded-For':'10.0.0.1','X-Forwarded-Host':'evil.example'})

    def test_registration_rate_limit_uses_visitor_ip_not_connector_or_xff(self):
        blocked=BrowserSession(self.origin,self.context,'192.0.2.31')
        fields=dict(invite_code='invalid-code-000000000000',username='attempt',password=PASSWORD,password_confirm=PASSWORD)
        for _ in range(12):
            self.ok(blocked,'/api/register',fields,status=400)
        self.ok(blocked,'/api/register',fields,{'X-Forwarded-For':'192.0.2.99'},status=429)
        other=BrowserSession(self.origin,self.context,'192.0.2.32')
        self.ok(other,'/api/register',fields,status=400)
        with closing(Database(self.database).connect()) as db:
            keys={row[0] for row in db.execute("SELECT DISTINCT key FROM attempts WHERE key LIKE 'register-ip:%'")}
        self.assertIn('register-ip:192.0.2.31',keys);self.assertIn('register-ip:192.0.2.32',keys)
        self.assertNotIn('register-ip:127.0.0.1',keys)
