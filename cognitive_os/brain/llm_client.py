from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import List, Dict


@dataclass(slots=True)
class LLMResponse:
    content: str
    model: str
    used_remote: bool


class LLMBrainClient:
    def __init__(self, model: str = "Pro/deepseek-ai/DeepSeek-V3.2") -> None:
        self.model = model

    def chat(self, messages: List[Dict[str, str]]) -> LLMResponse:
        api_key = os.getenv("SILICONFLOW_API_KEY", "")
        if not api_key:
            # deterministic local fallback
            user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
            return LLMResponse(content=f"[LOCAL_BRAIN] {user}", model="local-fallback", used_remote=False)

        payload = json.dumps({"model": self.model, "messages": messages}).encode("utf-8")
        req = urllib.request.Request(
            url="https://api.siliconflow.cn/v1/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError:
            user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
            return LLMResponse(content=f"[LOCAL_BRAIN_FALLBACK] {user}", model="local-fallback", used_remote=False)

        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return LLMResponse(content=content, model=self.model, used_remote=True)
