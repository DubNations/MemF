import urllib.request
import json

BASE = 'http://localhost:8000'

# 测试知识单元
print('测试知识单元 API...')
req = urllib.request.Request(
    f'{BASE}/api/knowledge',
    method='GET',
    headers={'Content-Type': 'application/json'}
)

try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        print(f'Status: {resp.status}')
        data = json.loads(resp.read().decode('utf-8'))
        print(f'知识单元数量: {len(data.get("items", []))}')
        for item in data.get("items", [])[:5]:
            print(f'  - {item.get("content", "")[:50]}...')
except Exception as e:
    print(f'Error: {e}')

# 测试文档上传到的场景
print('\n测试文档按场景分组...')
req = urllib.request.Request(
    f'{BASE}/api/documents?limit=100',
    method='GET',
    headers={'Content-Type': 'application/json'}
)

try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        items = data.get("items", [])
        scenarios = {}
        for doc in items:
            scenario = doc.get("scenario", "unknown")
            if scenario not in scenarios:
                scenarios[scenario] = 0
            scenarios[scenario] += 1
        print(f'场景分布: {scenarios}')
except Exception as e:
    print(f'Error: {e}')
