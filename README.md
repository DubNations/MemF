# Cognitive OS Kernel (MVP+)

## 1) 运行金融场景 Demo

```bash
python -m cognitive_os.demo.finance_case
```

该场景模拟 **贷款风险预审**：
- 初始知识低置信度
- Skill 自动补充信息
- Rule Engine 输出约束决策（例如 `require_manual_review`）

## 2) 启动可视化管理控制台

```bash
python -c "from cognitive_os.api.http_api import run_http_api; run_http_api()"
```

打开浏览器：
- `http://localhost:8000/`

页面可进行：
- Rule 管理（新增）
- KnowledgeUnit 管理（新增）
- Cognition Loop 运行
- 场景结果查看（finance）
- 当前系统状态查看（rules / knowledge / judgements）

## 3) API 概览

- `POST /api/rules`
- `GET /api/rules`
- `POST /api/knowledge`
- `GET /api/knowledge`
- `POST /cognition/run`
- `GET /api/judgements?limit=10`
- `GET /api/scenario/finance`
