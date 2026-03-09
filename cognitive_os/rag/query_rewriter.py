from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class RewriteResult:
    original_query: str
    rewritten_query: str
    keywords: List[str]
    intent: str
    confidence: float = 1.0


class QueryRewriter:
    SYNONYM_MAP: Dict[str, List[str]] = {
        "赚钱": ["收入", "盈利", "利润", "收益"],
        "花钱": ["支出", "消费", "开销"],
        "公司": ["企业", "组织", "机构"],
        "产品": ["商品", "服务", "解决方案"],
        "问题": ["疑问", "困惑", "难题"],
        "建议": ["推荐", "意见", "方案"],
        "最好": ["最优", "最佳", "推荐"],
        "怎么": ["如何", "怎样", "方法"],
        "为什么": ["原因", "为何", "缘由"],
        "什么时候": ["何时", "时间"],
    }

    STOPWORDS = {
        "的", "了", "是", "在", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
        "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
        "自己", "这", "那", "什么", "吗", "呢", "吧", "啊", "嗯", "哦", "哈",
    }

    INTENT_PATTERNS = {
        "definition": [r"什么是", r"定义", r"解释", r"意思"],
        "comparison": [r"区别", r"对比", r"比较", r"不同", r"差异"],
        "howto": [r"如何", r"怎么", r"怎样", r"方法", r"步骤"],
        "reason": [r"为什么", r"原因", r"为何"],
        "recommendation": [r"推荐", r"建议", r"最好", r"选择"],
        "calculation": [r"多少", r"计算", r"统计", r"数量"],
        "temporal": [r"什么时候", r"何时", r"时间", r"日期"],
    }

    def __init__(self, llm_client: Optional[Any] = None):
        self._llm_client = llm_client

    def rewrite(self, query: str, use_llm: bool = False) -> RewriteResult:
        keywords = self._extract_keywords(query)
        intent = self._detect_intent(query)

        if use_llm and self._llm_client:
            rewritten = self._rewrite_with_llm(query)
        else:
            rewritten = self._rewrite_rule_based(query, keywords)

        return RewriteResult(
            original_query=query,
            rewritten_query=rewritten,
            keywords=keywords,
            intent=intent,
        )

    def _extract_keywords(self, query: str) -> List[str]:
        words = re.findall(r"[\w]+", query)
        keywords = []
        for word in words:
            if word not in self.STOPWORDS and len(word) > 1:
                keywords.append(word)
                if word in self.SYNONYM_MAP:
                    keywords.extend(self.SYNONYM_MAP[word][:2])
        return list(set(keywords))

    def _detect_intent(self, query: str) -> str:
        for intent, patterns in self.INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, query):
                    return intent
        return "general"

    def _rewrite_rule_based(self, query: str, keywords: List[str]) -> str:
        rewritten = query

        for word, synonyms in self.SYNONYM_MAP.items():
            if word in query:
                rewritten = rewritten.replace(word, f"{word}({synonyms[0]})")

        if not query.endswith("?") and not query.endswith("？"):
            rewritten = rewritten + " " + " ".join(keywords[:3])

        return rewritten.strip()

    def _rewrite_with_llm(self, query: str) -> str:
        if not self._llm_client:
            return query

        try:
            prompt = f"""请将以下用户查询重写为更适合检索的形式。
要求：
1. 保留原始意图
2. 扩展同义词
3. 添加关键词
4. 保持简洁

原始查询：{query}

重写后的查询："""

            response = self._llm_client.chat(prompt)
            return response.strip() if response else query
        except Exception:
            return query

    def expand_for_retrieval(self, query: str) -> str:
        result = self.rewrite(query)
        expanded_parts = [result.rewritten_query]

        if result.keywords:
            expanded_parts.append("关键词: " + " ".join(result.keywords[:5]))

        return " ".join(expanded_parts)

    def normalize_query(self, query: str) -> str:
        normalized = query.lower()
        normalized = re.sub(r"[^\w\s\u4e00-\u9fff]", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized.strip()
