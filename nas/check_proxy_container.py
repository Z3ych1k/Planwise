"""CI: verify the production Gunicorn trust boundary on real Docker peer IPs.

Uses only randomly named test resources and no Cloudflare token/connection.
Requires planwise-nas:test. Run: python nas/check_proxy_container.py
"""
import json
import os
import subprocess
import time
import uuid


def docker(*args):
    return subprocess.check_output(['docker',*args],text=True).strip()


def probe(network,peer,script):
    return docker('run','--rm','--network',network,'--ip',peer,'--read-only','--cap-drop=ALL',
                  '--security-opt','no-new-privileges:true','--entrypoint','python','planwise-nas:test','-c',script)


if __name__ == '__main__':
    settings=json.loads(subprocess.check_output(['docker','compose','-f','compose.cloudflare.yaml','--profile','public','config','--format','json'],text=True,env=dict(os.environ,PLANWISE_PUBLIC_ORIGIN='https://planner.example.com')))
    app,connector=settings['services']['planwise'],settings['services']['cloudflared']
    assert app['build']['context']=='https://github.com/Z3ych1k/Planwise.git#feature/nas-cloudflare-oop'
    assert not app.get('ports') and not connector.get('ports')
    assert app['volumes'][0]['source']=='cloudflare-data' and not connector.get('volumes')
    assert app['environment']['PLANWISE_TRUSTED_PROXY_IPS']==connector['networks']['origin']['ipv4_address']
    assert app['environment']['PLANWISE_COOKIE_SECURE']=='1'
    assert settings['networks']['origin']['internal']
    assert connector['user']=='65532:65532' and not connector.get('privileged')
    assert connector['environment']['TUNNEL_TOKEN_FILE']=='/run/secrets/tunnel_token'
    print('Compose uses new source, an isolated volume/network, no host ports and file-only token injection.')
    suffix=uuid.uuid4().hex[:10]
    network,container,volume=('nas-proxy-'+suffix+'-'+part for part in ('net','app','data'))
    try:
        docker('network','create','--internal','--subnet','172.30.88.0/29',network)
        docker('volume','create',volume)
        docker('run','-d','--name',container,'--network',network,'--ip','172.30.88.2',
               '--health-interval=1s','--health-start-period=0s',
               '--read-only','--tmpfs','/tmp','--cap-drop=ALL','--security-opt','no-new-privileges:true',
               '-e','PLANWISE_PUBLIC_ORIGIN=https://planner.example.com','-e','PLANWISE_COOKIE_SECURE=1',
               '-e','PLANWISE_TRUSTED_PROXY_IPS=172.30.88.3','-v',volume+':/data','planwise-nas:test')
        for _ in range(30):
            status=json.loads(docker('inspect',container))[0]['State']['Health']['Status']
            if status=='healthy':
                break
            time.sleep(1)
        else:
            raise RuntimeError('Proxy-mode container did not become healthy.')
        shared="""
import http.client,json
c=http.client.HTTPConnection('172.30.88.2',8080,timeout=5)
h={'Host':'planner.example.com','X-Forwarded-Proto':'https','CF-Connecting-IP':'198.51.100.7','X-Forwarded-For':'10.0.0.1','X-Forwarded-Host':'evil.example'}
"""
        print(probe(network,'172.30.88.3',shared+"""
c.request('GET','/',headers=h);r=c.getresponse();assert r.status==200,r.read();r.read()
c.request('GET','/api/state',headers=h);r=c.getresponse();assert r.status==401,r.read();assert r.getheader('Cloudflare-CDN-Cache-Control')=='no-store';r.read()
h['X-Forwarded-Proto']='http'
c.request('GET','/api/state',headers=h);r=c.getresponse();assert r.status==403,r.read();r.read()
print('Trusted connector accepted; forged chain ignored; HTTP rejected; unauthenticated API private.')
"""))
        print(probe(network,'172.30.88.4',shared+"""
c.request('GET','/api/state',headers=h);r=c.getresponse();assert r.status==403,r.read();assert json.loads(r.read())['code']=='proxy'
print('Untrusted container with forged Cloudflare headers rejected.')
"""))
    except BaseException:
        subprocess.run(['docker','logs',container],check=False)
        raise
    finally:
        subprocess.run(['docker','rm','-f',container],check=False)
        subprocess.run(['docker','volume','rm',volume],check=False)
        subprocess.run(['docker','network','rm',network],check=False)
