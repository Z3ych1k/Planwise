"""Unit checks for the boundary before Flask sees forwarded request fields."""
from pathlib import Path
import tempfile
import unittest

from werkzeug.test import Client
from werkzeug.wrappers import Request, Response

from nas.application import create_app
from nas.proxy import tunnel_proxy


class ProxyTests(unittest.TestCase):
    def setUp(self):
        @Request.application
        def echo(request):
            return Response(f'{request.scheme}|{request.host}|{request.remote_addr}')
        self.echo = echo
        self.client = Client(tunnel_proxy(echo,'https://planner.example.com','172.30.77.3',True),Response)
        self.headers = {'Host':'planner.example.com','X-Forwarded-Proto':'https','CF-Connecting-IP':'2001:db8::7'}

    def get(self,headers=None,peer='172.30.77.3',path='/api/state'):
        return self.client.get(path,headers=self.headers if headers is None else headers,environ_overrides={'REMOTE_ADDR':peer})

    def test_only_exact_opted_in_peer_can_supply_cloudflare_fields(self):
        self.assertEqual(self.get().text,'https|planner.example.com|2001:db8::7')
        for peer in ('172.30.77.4','192.0.2.1','', 'not-an-ip'):
            result=self.get(peer=peer)
            self.assertEqual(result.status_code,403)
            self.assertIn('no-store',result.headers['Cache-Control'])

    def test_host_and_https_are_required_and_proxy_lists_are_not_accepted(self):
        for field,value in [('Host','evil.example'),('X-Forwarded-Proto','http'),('X-Forwarded-Proto','http, https'),('CF-Connecting-IP','bad'),('CF-Connecting-IP','192.0.2.1, 198.51.100.1')]:
            with self.subTest(field=field,value=value):
                result=self.get(dict(self.headers,**{field:value}))
                self.assertIn(result.status_code,(400,403))
        for field in ('CF-Connecting-IP','X-Forwarded-Proto'):
            headers=dict(self.headers);del headers[field]
            self.assertIn(self.get(headers).status_code,(400,403))

    def test_untrusted_forwarded_chain_host_and_port_do_not_change_identity(self):
        headers=dict(self.headers,**{'X-Forwarded-For':'10.0.0.1','X-Forwarded-Host':'evil.example','X-Forwarded-Port':'81','Forwarded':'for=10.0.0.1;host=evil.example;proto=http'})
        self.assertEqual(self.get(headers).text,'https|planner.example.com|2001:db8::7')

    def test_local_health_is_the_only_direct_exception(self):
        self.assertEqual(self.get({},'127.0.0.1','/healthz').status_code,200)
        self.assertEqual(self.get({},'127.0.0.1','/api/state').status_code,403)
        self.assertEqual(self.get({},'192.0.2.1','/healthz').status_code,403)

    def test_default_lan_mode_does_not_enable_header_trust(self):
        client=Client(tunnel_proxy(self.echo,'','',False),Response)
        result=client.get('/api/state',headers=self.headers,environ_overrides={'REMOTE_ADDR':'192.0.2.5'})
        self.assertEqual(result.text,'http|planner.example.com|192.0.2.5')

    def test_explicit_default_https_port_is_canonicalized(self):
        client=Client(tunnel_proxy(self.echo,'https://planner.example.com:443/','172.30.77.3',True),Response)
        for host in ('planner.example.com','planner.example.com:443'):
            result=client.get('/api/state',headers=dict(self.headers,Host=host),environ_overrides={'REMOTE_ADDR':'172.30.77.3'})
            self.assertEqual(result.text,'https|planner.example.com|2001:db8::7')

    def test_partial_or_unsafe_config_fails_closed_before_database_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'not-created.sqlite3'
            for origin,ips,secure in [('https://planner.example.com','',True),('','172.30.77.3',True),('http://planner.example.com','172.30.77.3',True),('https://planner.example.com/path','172.30.77.3',True),('https://user:pass@planner.example.com','172.30.77.3',True),('https://planner.example.com','*',True),('https://planner.example.com','0.0.0.0/0',True),('https://planner.example.com','172.30.77.3',False)]:
                with self.subTest(origin=origin,ips=ips,secure=secure),self.assertRaises(ValueError):
                    create_app(dict(DATABASE=str(path),PUBLIC_ORIGIN=origin,TRUSTED_PROXY_IPS=ips,COOKIE_SECURE=secure))
                self.assertFalse(path.exists())
