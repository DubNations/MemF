# Cognitive OS 个人知识助手

## 核心架构
- **模型为脑**：`PersonalKnowledgeAssistant` 负责需求理解、工具调度与答案生成。
- **知识为基**：DOC/PDF/PPTX/XLSX 解析后进入向量检索层，采用语义相似 + 置信/来源/冲突加权重排。
- **功能为手脚**：文档解析、规则推理、冲突处理、实验与遥测都作为模型可调用能力。

## 🆕 新增功能（借鉴自Quivr）

### 1. 文档解析增强
| 功能 | 描述 |
|------|------|
| **PPTX格式支持** | 支持PowerPoint演示文稿解析 |
| **XLSX格式支持** | 支持Excel表格解析 |
| **OCR支持** | 自动检测扫描版PDF并启用OCR |
| **表格提取** | 结构化提取表格数据并转换为Markdown |
| **智能解析策略** | FAST/HI_RES自动选择 |

### 2. RAG工作流优化
| 功能 | 描述 |
|------|------|
| **YAML工作流配置** | 可定制的RAG处理流程 |
| **查询重写** | 自动优化用户查询，扩展同义词 |
| **Reranker支持** | Cohere/Cross-Encoder/本地Reranker |
| **聊天历史管理** | 多轮对话上下文支持 |

### 3. 多用户权限支持
| 功能 | 描述 |
|------|------|
| **用户管理** | 用户注册、登录、API Key管理 |
| **权限系统** | 基于角色的访问控制(RBAC) |
| **资源权限** | 知识库级别的细粒度权限控制 |
| **知识库共享** | 支持知识库共享给其他用户 |

### 4. LLM生态扩展
| Provider | 支持模型 |
|----------|----------|
| **OpenAI** | gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-3.5-turbo |
| **Anthropic** | claude-3-5-sonnet, claude-3-opus, claude-3-haiku |
| **Mistral** | mistral-large, mistral-medium, mistral-small |
| **SiliconFlow** | DeepSeek-V3, Qwen2.5-72B |
| **Ollama** | llama3, qwen2, mistral (本地) |
| **Local** | 本地回退模式 |

## 快速运行

### 1) 启动服务
```bash
python -c "from cognitive_os.api.http_api import run_http_api; run_http_api()"
```
打开：`http://localhost:8000/`

### 2) 配置LLM（可选）
```bash
# SiliconFlow (默认)
export SILICONFLOW_API_KEY=your_api_key

# OpenAI
export OPENAI_API_KEY=your_api_key

# Anthropic
export ANTHROPIC_API_KEY=your_api_key

# Mistral
export MISTRAL_API_KEY=your_api_key
```
未配置时将使用本地 deterministic fallback。

### 3) 安装可选依赖（增强功能）
```bash
# 文档解析增强
pip install pdfplumber openpyxl

# OCR支持
pip install pytesseract pdf2image
# 还需安装Tesseract: https://github.com/tesseract-ocr/tesseract

# Reranker支持
pip install cohere  # Cohere Reranker
# 或
pip install sentence-transformers  # 本地Cross-Encoder

# LLM Provider支持
pip install openai  # OpenAI/SiliconFlow
pip install anthropic  # Anthropic
pip install mistralai  # Mistral
```

### 4) 核心用户路径
1. 上传文档到 `/api/documents/upload`（支持PDF/DOC/DOCX/PPTX/XLSX/TXT/MD/CSV）
2. 创建会话 `/api/sessions`
3. 用户输入自然语言需求到 `/api/assistant/query`
4. 系统自动执行：查询重写 → 向量检索 → Reranker重排 → 认知循环（按需）→ 大模型总结输出

## API 概览

### 文档管理
- `POST /api/documents/upload` - 上传文档（支持多种格式）
- `POST /api/documents/update` - 更新文档
- `POST /api/documents/delete` - 删除文档
- `GET /api/documents?limit=20` - 文档列表
- `GET /api/supported-formats` - 支持的文档格式

### 会话管理
- `POST /api/sessions` - 创建新会话
- `GET /api/sessions?knowledge_base_id=1` - 会话列表
- `GET /api/sessions/{session_id}` - 获取会话详情
- `POST /api/sessions/delete` - 删除会话

### 助手查询
- `POST /api/assistant/query` - 智能问答
  ```json
  {
    "query": "用户问题",
    "scenario": "general",
    "knowledge_base_id": 1,
    "session_id": "uuid",
    "use_history": true,
    "use_rewrite": true,
    "use_rerank": true
  }
  ```

### 用户管理（新增）
- `POST /api/users` - 创建用户
- `GET /api/users` - 用户列表
- `GET /api/users/{user_id}` - 用户详情
- `POST /api/users/login` - 用户登录
- `POST /api/users/api-keys` - 创建API Key
- `GET /api/users/api-keys` - API Key列表

### 权限管理（新增）
- `POST /api/permissions/grant` - 授予权限
- `POST /api/permissions/revoke` - 撤销权限
- `GET /api/permissions/check` - 检查权限
- `POST /api/knowledge-bases/{id}/share` - 共享知识库

### RAG配置
- `GET /api/rerankers` - 可用的Reranker列表
- `GET /api/llm-providers` - 可用的LLM Provider列表

### 其他API
- `GET /api/knowledge/search?q=关键词` - 知识检索
- `GET /api/judgements?limit=10` - 判决记录
- `GET /api/loop_runs?limit=10` - 循环运行记录
- `GET /api/reports/summary` - 实验报告
- `POST /api/experiments/run` - 运行实验

## 工作流配置

创建 `config/workflow.yaml` 自定义RAG流程：

```yaml
workflow_config:
  name: "cognitive_rag"
  nodes:
    - name: "START"
      edges: ["rewrite"]
    - name: "rewrite"
      edges: ["retrieve"]
    - name: "retrieve"
      edges: ["rerank"]
    - name: "rerank"
      edges: ["generate"]
    - name: "generate"
      edges: ["END"]

max_history: 10

reranker_config:
  supplier: "cohere"  # 或 "cross-encoder" 或 "local"
  model: "rerank-multilingual-v3.0"
  top_n: 5
  enabled: true

llm_config:
  max_input_tokens: 4000
  temperature: 0.7
```

## 9 场景验证

### 生成大样本数据（每场景 >1000）
```bash
python -m cognitive_os.experiments.generate_datasets
```

### 执行三轮验证—分类—处理
```bash
python -m cognitive_os.experiments.run_iterations
```
输出：
- `cognitive_os/experiments/reports/summary.json`
- `cognitive_os/experiments/reports/validation_report.md`

## 测试
```bash
python -m pytest -q
```

## 架构对比：Cognitive OS vs Quivr

| 特性 | Cognitive OS | Quivr |
|------|--------------|-------|
| 认知循环 | ✅ 自动推理+问题修复 | ❌ |
| 知识加权体系 | ✅ 置信度+来源+冲突惩罚 | ❌ |
| 规则引擎 | ✅ DSL条件推理 | ❌ |
| 技能系统 | ✅ 可插拔问题处理 | ❌ |
| 文档解析 | ✅ PDF/DOC/DOCX/PPTX/XLSX/OCR | ✅ Megaparse |
| Reranker | ✅ Cohere/Cross-Encoder/本地 | ✅ Cohere |
| 查询重写 | ✅ 规则+LLM | ✅ |
| 聊天历史 | ✅ SQLite | ✅ PostgreSQL |
| 多用户 | ✅ RBAC权限系统 | ✅ |
| LLM支持 | ✅ 6种Provider | ✅ 多种 |

## 核心创新（保持不变）
1. **认知循环** - 自动推理和问题修复
2. **知识加权体系** - 置信度+来源+冲突惩罚
3. **规则引擎** - DSL条件推理
4. **技能系统** - 可插拔的问题处理
5. **判决可追溯** - 完整的推理记录

## 新增模块结构

```
cognitive_os/
├── brain/
│   ├── llm_client.py          # 统一LLM客户端
│   └── llm_providers/         # LLM Provider实现
│       ├── __init__.py
│       └── providers.py       # OpenAI/Anthropic/Mistral/SiliconFlow/Ollama/Local
├── ingestion/
│   ├── document_pipeline.py   # 文档处理管道
│   └── parsers/               # 解析器实现
│       ├── base_parser.py     # 解析器基类
│       ├── native_parser.py   # 原生解析器
│       └── megaparse_adapter.py # Megaparse适配器
├── rag/
│   ├── workflow_config.py     # YAML工作流配置
│   ├── query_rewriter.py      # 查询重写
│   ├── reranker.py            # Reranker支持
│   └── chat_history.py        # 聊天历史管理
└── users/
    ├── user_manager.py        # 用户管理
    └── permission_manager.py  # 权限管理
```
