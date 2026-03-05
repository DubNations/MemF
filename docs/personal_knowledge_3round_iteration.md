# 个人知识服务：三轮验证—分类—处理记录

## 范围约束
- 仅聚焦个人知识服务。
- 9个真实细分场景（学习3 + 职业3 + 健康效率3）。
- 每个场景样本规模 > 1000（非玩具数据）。

## 九个场景
1. learning_exam_prep
2. learning_skill_transition
3. learning_language_retention
4. career_interview_prep
5. career_project_planning
6. career_networking
7. wellbeing_sleep_optimization
8. wellbeing_nutrition_tracking
9. wellbeing_focus_management

## 第1轮：有效性验证
### 判定标准
- 有用：在大样本下可稳定产出结构化决策，且延迟可接受。
- 可提升：可产出决策，但规则执行/冲突处理/技能执行存在稳定性隐患。
- 不可用：无法在规模化知识输入下可重复执行或出现不可追溯行为。

### 结果
- 有用：规则驱动决策、批量知识入库、可回放的判断记录。
- 可提升：规则表达安全性、冲突识别语义能力、技能执行隔离。
- 不可用：缺乏统一迭代报告与run级遥测，无法跨轮对比复现。

### 处理
- 固化有用能力：新增批量导入与去重、实验脚本单命令运行。
- 强化安全测试：DSL安全测试、技能超时测试。

## 第2轮：可提升项优化
### 问题
- eval规则引擎存在安全风险。
- 冲突仅识别低置信与缺失，缺乏矛盾主题识别。
- 所有技能全量执行，效率与稳定性不足。

### 优化落地
- 替换为AST白名单DSL执行器并输出诊断信息。
- 增加CONTRADICTION冲突类型（topic polarity冲突）。
- SkillManager增加类型路由 + 超时 + 错误隔离 + 执行报告。

## 第3轮：不可用点泛化重构
### 不可用根因
- 缺少跨轮运行遥测、不可形成可复现实验闭环。

### 泛化功能点
- run级别记录（loop_runs）、diagnostics持久化。
- 标准化实验产出（summary.json + validation_report.md）。
- 9场景统一数据生成器（固定随机种子，可稳定复现）。

## 最终状态
- 架构可在9个个人知识场景上进行稳定复现实验。
- 形成“验证—分类—处理”三轮闭环，具备可持续迭代能力。
