from __future__ import annotations

import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Dict, List

from cognitive_os.rules.rule import Rule


@dataclass(slots=True)
class BootstrapResult:
    rules: List[Rule]
    fetched_urls: List[str]
    errors: List[str]


DOMAIN_SOURCES: Dict[str, List[str]] = {
    "finance": [
        "https://www.reuters.com/markets/",
        "https://www.investopedia.com/financial-regulations-4689745",
        "https://www.bis.org/publ/othp31.htm",
    ],
    "supply_chain": [
        "https://www.supplychaindive.com/",
        "https://www.weforum.org/agenda/archive/supply-chain/",
        "https://www.investopedia.com/terms/s/supplychain.asp",
    ],
}


def _clean_html(raw: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", raw, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _split_sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[。！？.!?])\s+", text)
    return [p.strip() for p in parts if len(p.strip()) >= 40]


def _extract_rule_candidates(sentences: List[str]) -> List[Dict[str, str]]:
    candidates: List[Dict[str, str]] = []
    for s in sentences:
        low = s.lower()
        if any(k in low for k in ["must", "shall", "required", "禁止", "不得", "合规", "compliance"]):
            candidates.append({
                "scope": "compliance",
                "action_constraint": f"执行合规约束：{s[:120]}",
                "priority": "10",
                "condition": "knowledge_count >= 0",
            })
        if any(k in low for k in ["conflict", "contradict", "inconsistent", "冲突", "矛盾"]):
            candidates.append({
                "scope": "conflict_resolution",
                "action_constraint": f"触发冲突校验与人工复核：{s[:120]}",
                "priority": "9",
                "condition": "knowledge_count >= 2",
            })
        if any(k in low for k in ["expire", "expiry", "valid until", "effective date", "过期", "失效"]):
            candidates.append({
                "scope": "freshness",
                "action_constraint": f"触发时效校验：{s[:120]}",
                "priority": "8",
                "condition": "metadata['scenario'] != ''",
            })
    return candidates


def _fallback_templates(domain: str) -> List[Rule]:
    domain = domain or "general"
    return [
        Rule(
            id=f"tpl_{domain}_compliance_guard",
            scope="compliance",
            condition="knowledge_count >= 0",
            action_constraint="输出必须包含法规依据与风险提示；缺失时阻断自动执行",
            priority=10,
            applicable_boundary="global",
        ),
        Rule(
            id=f"tpl_{domain}_conflict_guard",
            scope="conflict_resolution",
            condition="knowledge_count >= 2",
            action_constraint="发现同主题冲突证据时，降低置信度并要求人工复核",
            priority=9,
            applicable_boundary="global",
        ),
        Rule(
            id=f"tpl_{domain}_expiry_guard",
            scope="freshness",
            condition="metadata['scenario'] != ''",
            action_constraint="如果知识超时效窗口则标记为待更新，不得作为唯一依据",
            priority=8,
            applicable_boundary="global",
        ),
    ]


def bootstrap_rules_from_web(domain: str, max_rules: int = 12, timeout_sec: int = 8) -> BootstrapResult:
    urls = DOMAIN_SOURCES.get(domain, [])
    fetched_urls: List[str] = []
    errors: List[str] = []
    collected: List[Rule] = []

    for idx, url in enumerate(urls):
        if len(collected) >= max_rules:
            break
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Connection": "close",
            })
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
            cleaned = _clean_html(raw)
            sentences = _split_sentences(cleaned[:100000])
            for cidx, c in enumerate(_extract_rule_candidates(sentences)[:4]):
                rule = Rule(
                    id=f"web_{domain}_{idx}_{cidx}",
                    scope=c["scope"],
                    condition=c["condition"],
                    action_constraint=c["action_constraint"],
                    priority=int(c["priority"]),
                    applicable_boundary="global",
                )
                collected.append(rule)
                if len(collected) >= max_rules:
                    break
            fetched_urls.append(url)
        except (urllib.error.URLError, TimeoutError, ValueError, Exception) as exc:
            errors.append(f"{url}: {str(exc)[:100]}")

    if not collected:
        collected = _fallback_templates(domain)[:max_rules]

    return BootstrapResult(rules=collected[:max_rules], fetched_urls=fetched_urls, errors=errors)
