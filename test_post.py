import urllib.request
import json

req = urllib.request.Request(
    'http://localhost:8000/api/assistant/query',
    data=json.dumps({'query': 'hello'}).encode('utf-8'),
    method='POST',
    headers={'Content-Type': 'application/json'}
)

try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        print(f'Status: {resp.status}')
        print(f'Response: {resp.read().decode("utf-8")[:1000]}')
except urllib.error.HTTPError as e:
    print(f'HTTP Error: {e.code}')
    print(f'Response: {e.read().decode("utf-8")[:500]}')
except Exception as e:
    print(f'Error: {e}')
