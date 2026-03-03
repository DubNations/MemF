# Cognitive OS Kernel (Personal Knowledge Service)

## 1) 生成9个真实规模场景数据（每个场景 > 1000 样本）

```bash
python -m cognitive_os.experiments.generate_datasets
```

## 2) 执行三轮验证—分类—处理迭代

```bash
python -m cognitive_os.experiments.run_iterations
```

输出文件：
- `cognitive_os/experiments/reports/summary.json`
- `cognitive_os/experiments/reports/validation_report.md`

## 3) API（含安全与批量能力）

```bash
python -c "from cognitive_os.api.http_api import run_http_api; run_http_api()"
```

可选安全：
```bash
export COGNITIVE_OS_API_TOKEN=your_token
```
请求时附带 Header：`X-API-Key: your_token`

接口：
- `POST /api/rules`
- `GET /api/rules`
- `POST /api/knowledge`
- `POST /api/knowledge/batch`
- `GET /api/knowledge`
- `POST /cognition/run`
- `GET /api/judgements?limit=10`
- `GET /api/loop_runs?limit=10`

## 4) 测试

```bash
python -m pytest -q
```

覆盖：
- DSL 安全执行
- Skill 超时与路由隔离
- 9场景数据生成可复现
