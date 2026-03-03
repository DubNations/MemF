# Cognitive OS Personal Knowledge Assistant

## 核心架构
- **模型为脑**：`PersonalKnowledgeAssistant` 负责需求理解、工具调度与答案生成。
- **知识为基**：DOC/PDF 解析后进入向量检索层，采用语义相似 + 置信/来源/冲突加权重排。
- **功能为手脚**：文档解析、规则推理、冲突处理、实验与遥测都作为模型可调用能力。

## 快速运行

### 1) 启动服务
```bash
python -c "from cognitive_os.api.http_api import run_http_api; run_http_api()"
```
打开：`http://localhost:8000/`

### 2) 可选配置远程大模型（SiliconFlow）
```bash
export SILICONFLOW_API_KEY=your_api_key
```
未配置时将使用本地 deterministic fallback。

### 3) 核心用户路径（个人知识服务）
1. 上传 DOC/PDF 到 `/api/documents/upload`
2. 用户输入自然语言需求到 `/api/assistant/query`
3. 系统自动执行：向量检索 → 知识加权重排 → cognition loop（按需）→ 大模型总结输出
4. 在 `/api/documents` `/api/judgements` `/api/loop_runs` 查看可追溯记录

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

## API 概览
- `POST /api/documents/upload`
- `POST /api/assistant/query`
- `GET /api/documents?limit=20`
- `GET /api/judgements?limit=10`
- `GET /api/loop_runs?limit=10`
- `GET /api/reports/summary`
- `POST /api/experiments/run`
- `GET /api/cases/marketing-assistant`

## 测试
```bash
python -m pytest -q
```
