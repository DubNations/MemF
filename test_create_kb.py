import urllib.request
import json

BASE = 'http://localhost:8000'

# 创建知识库
print('创建知识库...')
req = urllib.request.Request(
    f'{BASE}/api/knowledge-bases',
    data=json.dumps({
        'name': 'test_kb',
        'domain': 'general',
        'description': '测试知识库'
    }).encode('utf-8'),
    method='POST',
    headers={'Content-Type': 'application/json'}
)

try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        print(f'Status: {resp.status}')
        print(f'Response: {resp.read().decode("utf-8")[:500]}')
except Exception as e:
    print(f'Error: {e}')

# 列出知识库
print('\n列出知识库...')
req = urllib.request.Request(
    f'{BASE}/api/knowledge-bases',
    method='GET',
    headers={'Content-Type': 'application/json'}
)

try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        print(f'Status: {resp.status}')
        data = json.loads(resp.read().decode('utf-8'))
        print(f'知识库: {data}')
except Exception as e:
    print(f'Error: {e}')
