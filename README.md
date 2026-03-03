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
- `POST /api/knowledge/batch`
- `GET /api/knowledge`
- `POST /cognition/run`
- `GET /api/judgements?limit=10`
- `GET /api/scenario/finance`

## 4) CSV / JSON 导入格式说明

### JSON 批量导入（推荐）
`POST /api/knowledge/batch` 接收 `KnowledgeUnit[]`，每项会返回校验与入库结果。

示例：

```json
[
  {
    "id": "loan_case_1",
    "knowledge_type": "case",
    "content": {
      "text": "借款人信用分 610",
      "original_url": "https://pkm.example/loan/1",
      "note_id": "note-2024-01",
      "import_channel": "obsidian"
    },
    "source": "public",
    "confidence": 0.35,
    "valid_boundary": "global",
    "invalid_boundary": "",
    "conflict_ids": []
  }
]
```

### CSV 导入字段
CSV 头建议如下（可通过脚本/工具转换后调用 `POST /api/knowledge/batch`）：

```csv
id,knowledge_type,content_text,original_url,note_id,import_channel,source,confidence,valid_boundary,invalid_boundary,conflict_ids
loan_case_1,case,借款人信用分 610,https://pkm.example/loan/1,note-2024-01,obsidian,public,0.35,global,,
```

映射规则建议：
- `content_text` -> `content.text`
- `original_url` -> `content.original_url`
- `note_id` -> `content.note_id`
- `import_channel` -> `content.import_channel`
- `conflict_ids` 为空时映射为 `[]`，有多个值时可用 `;` 分隔后转数组。

## 5) PKM（Personal Knowledge Management）示例

一个典型 PKM 笔记（Obsidian / Notion 导出）可转成：

```json
{
  "id": "pkm_finance_note_2024_11_03",
  "knowledge_type": "insight",
  "content": {
    "text": "客户近 6 个月信用分持续下降，且近 2 月负债率上升。",
    "original_url": "https://notes.example/personal/finance-risk-review",
    "note_id": "obsidian://vault/Finance/RiskReview#2024-11-03",
    "import_channel": "notion_export"
  },
  "source": "private_notes",
  "confidence": 0.62,
  "valid_boundary": "global",
  "invalid_boundary": "",
  "conflict_ids": []
}
```

系统会在入库前执行内容归一化去重（大小写、空白与 JSON 键顺序规整后计算内容哈希），重复内容会合并并标记为失败项返回。
