import json
import urllib.request
from urllib.error import HTTPError, URLError

URL = 'http://127.0.0.1:8000'

req = urllib.request.Request(URL + '/api/grants?refresh=true', data=json.dumps({'prompt':'diagnostic'}).encode('utf-8'), headers={'Content-Type':'application/json','x-internal-key':'base-nav-dev-secret-1819'})
try:
    with urllib.request.urlopen(req, timeout=120) as r:
        print('STATUS', r.status)
        print(r.read().decode())
except HTTPError as e:
    try:
        print('HTTPERROR', e.code)
        print(e.read().decode())
    except Exception:
        print('HTTPERROR', e.code)
except URLError as e:
    print('URLERROR', e.reason)
except Exception as e:
    print('ERROR', e)
