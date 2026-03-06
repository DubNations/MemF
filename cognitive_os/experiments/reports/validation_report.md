# Personal Knowledge Service: 3-Round Validation & Iteration

- Total scenarios: 9
- Domain focus: Personal Knowledge Service only

## Scenario-level metrics

| Scenario | Persona | Sample Size | Latency (ms) | Decisions | Diagnostics | Lookup Gain % | Error Reduction % |
|---|---|---:|---:|---:|---:|---:|---:|
| career_project_retrospective | 项目复盘教练 | 1400 | 545 | 2 | 0 | 69.8 | 57.9 |
| career_transition_advisor | 职业转型顾问 | 1500 | 869 | 2 | 0 | 68.4 | 57.9 |
| education_exam_coach | 考试备考教练 | 1650 | 1289 | 2 | 0 | 66.7 | 57.9 |
| efficiency_focus_coach | 专注力教练 | 1450 | 1701 | 2 | 0 | 64.9 | 57.9 |
| finance_insurance_consultant | 保险咨询师 | 1550 | 1940 | 2 | 0 | 63.9 | 57.9 |
| finance_wealth_advisor | 个人理财顾问 | 1700 | 2437 | 2 | 0 | 61.8 | 57.9 |
| health_chronic_care_manager | 慢病患者管理师 | 1600 | 3041 | 2 | 0 | 59.3 | 57.9 |
| health_nutrition_planner | 家庭营养管理师 | 1500 | 3187 | 2 | 0 | 58.8 | 57.9 |
| marketing_customer_service_assistant | 营销客服助手 | 1800 | 4161 | 3 | 0 | 60.4 | 57.9 |

## Iteration records
### round_1_validation (复盘执行偏差与可用性验证)
- Problem: 缺少真实入口与大样本验证
- Actions: DOC/PDF 入库能力, 大样本场景验证
- Useful: career_project_retrospective, career_transition_advisor, education_exam_coach, efficiency_focus_coach, finance_insurance_consultant, finance_wealth_advisor, health_chronic_care_manager, health_nutrition_planner, marketing_customer_service_assistant
- Improvable: None
- Unusable: None

### round_2_optimization (营销客服助手效率优化)
- Problem: 制度检索慢、回复一致性不足
- Actions: 制度文档结构化, strict_policy_response_mode
- Useful: career_project_retrospective, career_transition_advisor, education_exam_coach, efficiency_focus_coach, finance_insurance_consultant, finance_wealth_advisor, marketing_customer_service_assistant
- Improvable: health_chronic_care_manager, health_nutrition_planner
- Unusable: None

### round_3_generalization (9场景泛化与可复现)
- Problem: 跨身份泛化能力与稳定复现要求
- Actions: 统一实验模板, 标准化报告输出
- Useful: career_project_retrospective, career_transition_advisor, education_exam_coach
- Improvable: efficiency_focus_coach, finance_insurance_consultant, finance_wealth_advisor
- Unusable: health_chronic_care_manager, health_nutrition_planner, marketing_customer_service_assistant
