import requests
import json
import traceback

BASE = 'http://localhost:8000'

print('=' * 60)
print('API 端点详细测试')
print('=' * 60)

# 1. 测试知识库列表
print('\n1. 测试知识库列表 API...')
try:
    r = requests.get(f'{BASE}/api/knowledge-bases', timeout=5)
    print(f'状态码: {r.status_code}')
    print(f'响应: {r.text[:500]}')
except Exception as e:
    print(f'错误: {e}')

# 2. 测试模型对话
print('\n2. 测试模型对话 API...')
try:
    r = requests.post(f'{BASE}/api/assistant/query', json={
        'query': '你好',
        'scenario': 'general'
    }, timeout=15)
    print(f'状态码: {r.status_code}')
    print(f'响应: {r.text[:1000]}')
except Exception as e:
    print(f'错误: {type(e).__name__}: {e}')
    traceback.print_exc()

# 3. 测试规则引导
print('\n3. 测试规则引导 API...')
try:
    r = requests.post(f'{BASE}/api/rules/bootstrap', json={
        'domain': 'finance',
        'max_rules': 3
    }, timeout=15)
    print(f'状态码: {r.status_code}')
    print(f'响应: {r.text[:500]}')
except Exception as e:
    print(f'错误: {e}')

# 4. 测试文档上传
print('\n4. 测试文档上传 API...')
try:
    import base64
    test_content = b'Hello World PDF Test'
    test_b64 = base64.b64encode(test_content).decode('utf-8')

    r = requests.post(f'{BASE}/api/documents/upload', json={
        'filename': 'test.txt',
        'content_base64': test_b64,
        'scenario': 'test'
    }, timeout=15)
    print(f'状态码: {r.status_code}')
    print(f'响应: {r.text[:500]}')
except Exception as e:
    print(f'错误: {e}')

# 5. 测试会话创建
print('\n5. 测试会话创建 API...')
try:
    r = requests.post(f'{BASE}/api/sessions', json={}, timeout=5)
    print(f'状态码: {r.status_code}')
    print(f'响应: {r.text[:500]}')
except Exception as e:
    print(f'错误: {e}')

print('\n' + '=' * 60)
print('测试完成')
print('=' * 60)
