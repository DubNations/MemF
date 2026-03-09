# 测试 PDF 解析
print('测试 PDF 解析...')
from cognitive_os.ingestion.parsers import MegaparseAdapter

adapter = MegaparseAdapter()
print(f'pdfplumber 可用: {adapter._pdfplumber_available}')
print(f'pypdf 可用: {adapter._pypdf_available}')

# 创建一个简单的 PDF 测试
test_pdf = b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>\nendobj\n4 0 obj\n<< /Length 44 >>\nstream\nBT /F1 12 Tf 100 700 Td (Hello World) Tj ET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\n0000000214 00000 n\ntrailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n307\n%%EOF'

result = adapter.parse(test_pdf, 'test.pdf')
print(f'解析结果: success={result.success}, text_len={len(result.text)}, error={result.error}')
if result.text:
    print(f'解析文本: {result.text[:100]}')
else:
    print('解析文本: (empty)')

# 测试规则引导
print('\n测试规则引导...')
from cognitive_os.rules.rule_bootstrap import bootstrap_rules_from_web

result = bootstrap_rules_from_web('finance', max_rules=3)
print(f'规则数量: {len(result.rules)}')
print(f'获取的URL: {result.fetched_urls}')
print(f'错误: {result.errors}')
if result.rules:
    print(f'第一个规则: {result.rules[0].id} - {result.rules[0].scope}')

# 测试模型对话
print('\n测试模型对话...')
from cognitive_os.brain.llm_client import LLMBrainClient

client = LLMBrainClient()
print(f'API Key 配置: {"已配置" if client.api_key else "未配置"}')
print(f'Provider: {client.provider_name}')
print(f'Model: {client.model}')

# 测试本地回退
response = client.complete('你好，请介绍一下你自己')
print(f'回复: {response.content[:200]}...')
print(f'使用远程模型: {response.used_remote}')
