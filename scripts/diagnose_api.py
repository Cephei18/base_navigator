import json
import urllib.request
from urllib.error import HTTPError

URL = 'http://127.0.0.1:8000'

def post(path, headers=None):
    data = json.dumps({'prompt':'diagnostic sample'}).encode('utf-8')
    req = urllib.request.Request(URL + path, data=data, headers=headers or {'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            body = r.read().decode('utf-8')
            print(path, 'STATUS', r.status)
            print(body)
    except HTTPError as e:
        try:
            body = e.read().decode('utf-8')
        except Exception:
            body = ''
        print(path, 'HTTPERROR', e.code)
        print(body)
    except Exception as e:
        print(path, 'ERROR', str(e))

if __name__ == '__main__':
    print('POST without internal key')
    post('/api/governance')
    print('\nPOST with internal key')
    post('/api/governance', headers={'Content-Type':'application/json','x-internal-key':'base-nav-dev-secret-1819'})
    print('\nPOST grants without internal key')
    post('/api/grants')
    print('\nPOST grants with internal key')
    post('/api/grants', headers={'Content-Type':'application/json','x-internal-key':'base-nav-dev-secret-1819'})
