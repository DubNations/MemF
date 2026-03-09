import requests

BASE = 'http://localhost:8000'

print('=' * 60)
print('Cognitive OS API 全面功能检查')
print('=' * 60)

# 基础端点
print('\n[基础端点]')
print('1. 主页:', requests.get(BASE + '/').status_code == 200)
print('2. 模型配置:', requests.get(BASE + '/api/model-configs').status_code == 200)
print('3. 知识库:', requests.get(BASE + '/api/knowledge-bases').status_code == 200)
print('4. 规则:', requests.get(BASE + '/api/rules').status_code == 200)
print('5. 知识单元:', requests.get(BASE + '/api/knowledge').status_code == 200)
print('6. 文档:', requests.get(BASE + '/api/documents').status_code == 200)

# AnythingLLM 新功能
print('\n[AnythingLLM 新功能]')
print('7. Slash Commands:', requests.get(BASE + '/api/commands').status_code == 200)
print('8. 向量缓存:', requests.get(BASE + '/api/vector-cache/stats').status_code == 200)
print('9. Rerankers:', requests.get(BASE + '/api/rerankers').status_code == 200)
print('10. 支持格式:', requests.get(BASE + '/api/supported-formats').status_code == 200)

# 详细信息
print('\n[详细信息]')
r = requests.get(BASE + '/api/commands')
if r.status_code == 200:
    print('内置命令数量:', len(r.json().get('builtin', [])))

r = requests.get(BASE + '/api/supported-formats')
if r.status_code == 200:
    print('支持格式:', ', '.join(r.json().get('formats', [])))

r = requests.get(BASE + '/api/rerankers')
if r.status_code == 200:
    print('可用Rerankers:', r.json().get('available', []))

# 会话管理
print('\n[会话管理]')
r = requests.post(BASE + '/api/sessions', json={})
sid = r.json().get('session_id') if r.status_code == 201 else None
print('11. 创建会话:', r.status_code == 201, 'ID:', sid[:8] if sid else 'N/A')

if sid:
    print('12. 获取会话:', requests.get(f'{BASE}/api/sessions/{sid}').status_code == 200)
    print('13. 固定文档列表:', requests.get(f'{BASE}/api/sessions/{sid}/pinned').status_code == 200)
    r = requests.post(f'{BASE}/api/sessions/pin', json={'session_id': sid, 'document_id': 1, 'filename': 'test.pdf'})
    print('14. 固定文档:', r.status_code == 201)
    print('15. 验证固定:', requests.get(f'{BASE}/api/sessions/{sid}/pinned').status_code == 200)

print('\n' + '=' * 60)
print('所有功能检查完成!')
print('=' * 60)
