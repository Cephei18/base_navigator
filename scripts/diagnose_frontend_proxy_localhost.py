import json
import urllib.request
from urllib.error import HTTPError, URLError

URL = 'http://localhost:5174'

def post(path, headers=None, timeout=15):
    data = json.dumps({'prompt':'proxy diagnostic'}).encode('utf-8')
    req = urllib.request.Request(URL + path, data=data, headers=headers or {'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            print(path, 'STATUS', r.status)
            print(r.read().decode())
    except HTTPError as e:
        try:
            print(path, 'HTTPERROR', e.code)
            print(e.read().decode())
        except Exception:
            print(path, 'HTTPERROR', e.code)
    except URLError as e:
        print(path, 'URLERROR', e.reason)
    except Exception as e:
        print(path, 'ERROR', e)

if __name__ == '__main__':
    print('POST via dev server without explicit internal key (proxy should add it)')
    post('/api/governance')
    post('/api/grants')
