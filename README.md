# Cognitive OS Kernel (Personal Knowledge Service)

<<<<<<< codex/review-cognitive-os-kernel-implementation-specs-cuyls0
## 快速运行

### 1) 启动产品化控制台

```bash
python -c "from cognitive_os.api.http_api import run_http_api; run_http_api()"
```

打开：`http://localhost:8000/`

### 2) 个人用户标准路径（DOC/PDF）
1. 在 **个人工作流** 页签上传 DOC/PDF。
2. 系统执行：`文档解析 -> 结构化分块 -> KnowledgeUnit 入库`。
3. 执行 cognition loop 获取决策与约束建议。
4. 在遥测页查看 Documents / Judgements / Loop Runs。

## 数据与实验

### 3) 生成 9 个真实场景大样本（每场景 >1000）
=======
## 1) 生成9个真实规模场景数据（每个场景 > 1000 样本）
>>>>>>> main

```bash
python -m cognitive_os.experiments.generate_datasets
```

<<<<<<< codex/review-cognitive-os-kernel-implementation-specs-cuyls0
### 4) 执行三轮验证—分类—处理迭代
=======
## 2) 执行三轮验证—分类—处理迭代
>>>>>>> main

```bash
python -m cognitive_os.experiments.run_iterations
```

<<<<<<< codex/review-cognitive-os-kernel-implementation-specs-cuyls0
输出：
- `cognitive_os/experiments/reports/summary.json`
- `cognitive_os/experiments/reports/validation_report.md`

## API（含安全、上传、实验）
=======
输出文件：
- `cognitive_os/experiments/reports/summary.json`
- `cognitive_os/experiments/reports/validation_report.md`

## 3) API（含安全与批量能力）

```bash
python -c "from cognitive_os.api.http_api import run_http_api; run_http_api()"
```
>>>>>>> main

可选安全：
```bash
export COGNITIVE_OS_API_TOKEN=your_token
```
<<<<<<< codex/review-cognitive-os-kernel-implementation-specs-cuyls0
请求附带 Header：`X-API-Key: your_token`
=======
请求时附带 Header：`X-API-Key: your_token`
>>>>>>> main

接口：
- `POST /api/rules`
- `GET /api/rules`
- `POST /api/knowledge`
- `POST /api/knowledge/batch`
- `GET /api/knowledge`
<<<<<<< codex/review-cognitive-os-kernel-implementation-specs-cuyls0
- `POST /api/documents/upload`  # DOC/PDF 上传解析
- `GET /api/documents?limit=20`
=======
>>>>>>> main
- `POST /cognition/run`
- `GET /api/judgements?limit=10`
- `GET /api/loop_runs?limit=10`
- `GET /api/reports/summary`
- `POST /api/experiments/run`
<<<<<<< codex/review-cognitive-os-kernel-implementation-specs-cuyls0
- `GET /api/cases/marketing-assistant`

## 测试
=======

## 4) 测试
>>>>>>> main

```bash
python -m pytest -q
```

覆盖：
<<<<<<< codex/review-cognitive-os-kernel-implementation-specs-cuyls0
- DOC/PDF 文档解析与映射
=======
>>>>>>> main
- DSL 安全执行
- Skill 超时与路由隔离
- 9场景数据生成可复现
