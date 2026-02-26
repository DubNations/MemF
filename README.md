# MemF

当前仓库提供下一阶段落地方案文档：

- `docs/next-steps-plan.md`：
  - 管理端可视化建设建议
  - 用户绑定知识（多租户隔离）方案
  - 金融示例场景与评测设计
  - 4周执行路线图
# Cognitive OS Kernel (MVP)

## Run Demo

```bash
python -m cognitive_os.demo.simple_case
```

## Run HTTP API

```bash
python -c "from cognitive_os.api.http_api import run_http_api; run_http_api()"
```

POST `http://localhost:8000/cognition/run`

```json
{
  "goal": "demo goal",
  "boundary": "global",
  "metadata": {}
}
```
