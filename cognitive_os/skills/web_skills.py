from __future__ import annotations

import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from cognitive_os.ontology.ontology_entity import KnowledgeUnit
from cognitive_os.skills.base import BaseSkill


@dataclass
class WebPage:
    url: str
    title: str
    content: str
    links: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_knowledge_unit(self, source: str = "public") -> KnowledgeUnit:
        return KnowledgeUnit(
            id=f"web_{hash(self.url) % 10000000}",
            knowledge_type="case",
            content={
                "topic": self.title,
                "polarity": "pro",
                "summary": self.content[:2000],
                "url": self.url,
                "links": self.links[:10],
            },
            source=source,
            confidence=0.5,
            valid_boundary="global",
        )


class WebBrowsingSkill(BaseSkill):
    name = "web_browsing"
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query or URL"},
            "max_results": {"type": "integer", "default": 3},
            "timeout": {"type": "integer", "default": 10},
        },
        "required": ["query"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "pages": {"type": "array"},
            "summary": {"type": "string"},
        },
    }
    permission = "read_only"

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    ]

    def execute(self, issue_context: Dict[str, Any]) -> List[KnowledgeUnit]:
        query = issue_context.get("query", "")
        max_results = issue_context.get("max_results", 3)
        timeout = issue_context.get("timeout", 10)

        if self._is_url(query):
            page = self._fetch_page(query, timeout)
            if page:
                return [page.to_knowledge_unit()]
            return []

        search_results = self._search_web(query, max_results)
        units: List[KnowledgeUnit] = []
        for result in search_results[:max_results]:
            units.append(result.to_knowledge_unit())

        return units

    def _is_url(self, text: str) -> bool:
        url_pattern = r"^https?://"
        return bool(re.match(url_pattern, text, re.IGNORECASE))

    def _fetch_page(self, url: str, timeout: int = 10) -> Optional[WebPage]:
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": self.USER_AGENTS[0],
                    "Accept": "text/html,application/xhtml+xml",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
                html = response.read().decode("utf-8", errors="ignore")

            title = self._extract_title(html)
            content = self._extract_content(html)
            links = self._extract_links(html, url)

            return WebPage(
                url=url,
                title=title,
                content=content,
                links=links,
                metadata={"status": response.status},
            )
        except Exception:
            return None

    def _search_web(self, query: str, max_results: int) -> List[WebPage]:
        pages: List[WebPage] = []
        search_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"

        try:
            req = urllib.request.Request(
                search_url,
                headers={"User-Agent": self.USER_AGENTS[0]},
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                html = response.read().decode("utf-8", errors="ignore")

            result_pattern = r'<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>([^<]+)</a>'
            matches = re.findall(result_pattern, html)

            for url, title in matches[:max_results]:
                if url.startswith("http"):
                    page = self._fetch_page(url)
                    if page:
                        pages.append(page)

        except Exception:
            pass

        return pages

    def _extract_title(self, html: str) -> str:
        title_match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
        return title_match.group(1).strip() if title_match else "Untitled"

    def _extract_content(self, html: str) -> str:
        html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<nav[^>]*>.*?</nav>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<footer[^>]*>.*?</footer>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<header[^>]*>.*?</header>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<[^>]+>", " ", html)
        html = re.sub(r"\s+", " ", html)
        return html.strip()[:5000]

    def _extract_links(self, html: str, base_url: str) -> List[str]:
        link_pattern = r'href="(https?://[^"]+)"'
        links = re.findall(link_pattern, html)
        unique_links = list(set(links))
        return [l for l in unique_links if l != base_url][:20]


class URLParserSkill(BaseSkill):
    name = "url_parser"
    input_schema = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to parse"},
            "timeout": {"type": "integer", "default": 10},
        },
        "required": ["url"],
    }
    output_schema = {
        "type": "object",
        "properties": {
            "content": {"type": "string"},
            "metadata": {"type": "object"},
        },
    }
    permission = "read_only"

    def execute(self, issue_context: Dict[str, Any]) -> List[KnowledgeUnit]:
        url = issue_context.get("url", "")
        timeout = issue_context.get("timeout", 10)

        if not url:
            return []

        page = self._fetch_and_parse(url, timeout)
        if page:
            return [page.to_knowledge_unit()]
        return []

    def _fetch_and_parse(self, url: str, timeout: int) -> Optional[WebPage]:
        return WebBrowsingSkill()._fetch_page(url, timeout)


import urllib.parse
