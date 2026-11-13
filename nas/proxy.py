"""Opt-in Cloudflare origin boundary; never trust client-supplied proxy chains."""
from ipaddress import ip_address
import json
from urllib.parse import urlsplit

from werkzeug.wrappers import Response


def tunnel_proxy(application, origin, trusted_ips, secure_cookie):
    if not origin and not trusted_ips:
        return application
    try:
        public = urlsplit(origin)
        if (public.scheme != 'https' or not public.hostname or public.username is not None
                or public.password is not None or public.query or public.fragment
                or public.path not in ('','/') or (public.port is not None and not 1 <= public.port <= 65535)
                or any(char.isspace() for char in origin) or '\\' in origin):
            raise ValueError()
        peers = {ip_address(value.strip()) for value in trusted_ips.split(',')}
        if not peers or not secure_cookie:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise ValueError('Tunnel mode requires PUBLIC_ORIGIN=https://host, exact TRUSTED_PROXY_IPS and COOKIE_SECURE=1.') from None
    host = public.netloc.lower()

    def denied(environ, start_response, status, message):
        return Response(json.dumps(dict(error=message,code='proxy')),status=status,
                        content_type='application/json',headers={'Cache-Control':'private, no-store',
                        'Cloudflare-CDN-Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})(environ,start_response)

    def verified(environ, start_response):
        try:
            peer = ip_address(environ.get('REMOTE_ADDR',''))
        except ValueError:
            peer = None
        # Container health checks stay local and carry no account data.
        if (peer is not None and peer.is_loopback and environ.get('PATH_INFO') == '/healthz'
                and environ.get('REQUEST_METHOD') == 'GET'):
            return application(environ,start_response)
        if peer not in peers:
            return denied(environ,start_response,403,'Untrusted origin connection.')
        if environ.get('HTTP_HOST','').lower() != host:
            return denied(environ,start_response,400,'Unexpected public hostname.')
        if environ.get('HTTP_X_FORWARDED_PROTO') != 'https':
            return denied(environ,start_response,403,'HTTPS is required at the tunnel edge.')
        try:
            visitor = ip_address(environ.get('HTTP_CF_CONNECTING_IP',''))
        except ValueError:
            return denied(environ,start_response,400,'A single Cloudflare visitor IP is required.')
        # Cloudflare overwrites these two fields; X-Forwarded-For/Host are not trusted.
        environ['REMOTE_ADDR'] = str(visitor)
        environ['wsgi.url_scheme'] = 'https'
        environ['HTTP_HOST'] = host
        environ['SERVER_NAME'] = public.hostname
        environ['SERVER_PORT'] = str(public.port or 443)
        return application(environ,start_response)

    return verified
