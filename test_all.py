import urllib.request
import json

BASE = 'http://localhost:8000'

# 配置API Key
print('1. 配置API Key...')
req = urllib.request.Request(
    f'{BASE}/api/model-configs',
    data=json.dumps({
        'api_key': 'sk-heqwsuynodxbtlyuxyyvkgmmwsplhivkwzfhikhixpypyvsh',
        'name': 'siliconflow-deepseek',
        'provider': 'siliconflow',
        'model': 'Pro/deepseek-ai/DeepSeek-V3.2',
        'is_default': True
    }).encode('utf-8'),
    method='POST',
    headers={'Content-Type': 'application/json'}
)

try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        print(f'Status: {resp.status}')
        print(f'Response: {resp.read().decode("utf-8")[:200]}')
except Exception as e:
    print(f'Error: {e}')

# 测试知识库列表
print('\n2. 测试知识库列表...')
req = urllib.request.Request(
    f'{BASE}/api/knowledge-bases',
    method='GET',
    headers={'Content-Type': 'application/json'}
)

try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        print(f'Status: {resp.status}')
        data = json.loads(resp.read().decode('utf-8'))
        print(f'知识库数量: {len(data.get("items", []))}')
        print(f'知识库列表: {data.get("items", [])}')
except Exception as e:
    print(f'Error: {e}')

# 测试文档列表
print('\n3. 测试文档列表...')
req = urllib.request.Request(
    f'{BASE}/api/documents',
    method='GET',
    headers={'Content-Type': 'application/json'}
)

try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        print(f'Status: {resp.status}')
        data = json.loads(resp.read().decode('utf-8'))
        print(f'文档数量: {len(data.get("items", []))}')
        for doc in data.get("items", [])[:5]:
            print(f'  - {doc.get("filename")} (状态: {doc.get("status")})')
except Exception as e:
    print(f'Error: {e}')
