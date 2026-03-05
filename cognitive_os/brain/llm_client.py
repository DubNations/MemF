from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(slots=True)
class LLMResponse:
    content: str
    model: str
    used_remote: bool


class LLMBrainClient:
    def __init__(
        self,
        model: str = "Pro/deepseek-ai/DeepSeek-V3.2",
        api_key: Optional[str] = None,
        timeout_sec: int = 45,
        temperature: float = 0.2,
        context_window: int = 8192,
    ) -> None:
        self.model = model
        self.api_key = api_key or os.getenv("SILICONFLOW_API_KEY", "")
        self.timeout_sec = timeout_sec
        self.temperature = temperature
        self.context_window = context_window

    @staticmethod
    def _local_fallback(messages: List[Dict[str, str]], prefix: str = "[LOCAL_BRAIN]") -> LLMResponse:
        user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        return LLMResponse(content=f"{prefix} {user}", model="local-fallback", used_remote=False)

    def healthcheck(self) -> bool:
        if not self.api_key:
            return False
        resp = self.chat(
            [
                {"role": "system", "content": "healthcheck"},
                {"role": "user", "content": "ping"},
            ]
        )
        return resp.used_remote

    def chat(self, messages: List[Dict[str, str]]) -> LLMResponse:
        if not self.api_key:
            return self._local_fallback(messages)

        payload = json.dumps(
            {
                "model": self.model,
                "temperature": self.temperature,
                "max_tokens": max(512, min(4096, self.context_window // 2)),
                "messages": messages,
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            url="https://api.siliconflow.cn/v1/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError:
            return self._local_fallback(messages, prefix="[LOCAL_BRAIN_FALLBACK]")

        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return LLMResponse(content=content, model=self.model, used_remote=True)
