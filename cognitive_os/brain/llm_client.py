from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from cognitive_os.brain.llm_providers import (
    BaseLLMProvider,
    LLMConfig,
    LLMMessage,
    LLMProvider,
    LLMProviderFactory,
    LLMResponse as ProviderResponse,
)


@dataclass(slots=True)
class LLMResponse:
    content: str
    model: str
    used_remote: bool
    provider: str = "siliconflow"
    usage: Dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        if self.usage is None:
            self.usage = {}


class LLMBrainClient:
    PROVIDER_MAP = {
        "openai": LLMProvider.OPENAI,
        "anthropic": LLMProvider.ANTHROPIC,
        "mistral": LLMProvider.MISTRAL,
        "siliconflow": LLMProvider.SILICONFLOW,
        "ollama": LLMProvider.OLLAMA,
        "local": LLMProvider.LOCAL,
    }

    def __init__(
        self,
        model: str = "Pro/deepseek-ai/DeepSeek-V3.2",
        api_key: Optional[str] = None,
        timeout_sec: int = 45,
        temperature: float = 0.2,
        context_window: int = 8192,
        provider: str = "siliconflow",
        base_url: Optional[str] = None,
    ) -> None:
        self.model = model
        self.api_key = api_key or os.getenv("SILICONFLOW_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
        self.timeout_sec = timeout_sec
        self.temperature = temperature
        self.context_window = context_window
        self.provider_name = provider.lower()
        self.base_url = base_url
        self._provider_instance: Optional[BaseLLMProvider] = None

    def _get_provider(self) -> BaseLLMProvider:
        if self._provider_instance is not None:
            return self._provider_instance

        provider_type = self.PROVIDER_MAP.get(self.provider_name, LLMProvider.SILICONFLOW)

        config = LLMConfig(
            model=self.model,
            api_key=self.api_key,
            base_url=self.base_url,
            temperature=self.temperature,
            max_tokens=max(512, min(4096, self.context_window // 2)),
            timeout=self.timeout_sec,
            context_window=self.context_window,
        )

        self._provider_instance = LLMProviderFactory.create(provider_type, config)
        return self._provider_instance

    def set_provider(self, provider: str, model: Optional[str] = None, api_key: Optional[str] = None) -> None:
        self.provider_name = provider.lower()
        if model:
            self.model = model
        if api_key:
            self.api_key = api_key
        self._provider_instance = None

    @staticmethod
    def _local_fallback(messages: List[Dict[str, str]], prefix: str = "[LOCAL_BRAIN]") -> LLMResponse:
        user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        keywords = ["建议", "决策", "下一步", "策略", "方案", "总结"]
        if any(k in user for k in keywords):
            content = (
                f"{prefix}\n"
                "1. 结论: 基于现有知识库分析，建议进一步收集信息。\n"
                "2. 依据: 当前查询触发了认知循环，但本地模式无法进行深度推理。\n"
                "3. 风险提示: 本地回退模式功能有限，建议配置远程LLM。\n"
                "4. 下一步行动: 配置API密钥以获得完整功能。"
            )
        else:
            content = f"{prefix} 本地回退模式。请配置API密钥以获得完整功能。\n您的问题: {user[:100]}..."

        return LLMResponse(
            content=content,
            model="local-fallback",
            used_remote=False,
            provider="local",
        )

    def healthcheck(self) -> bool:
        if not self.api_key and self.provider_name != "local":
            return False
        try:
            provider = self._get_provider()
            return provider.healthcheck()
        except Exception:
            return False

    def chat(self, messages: List[Dict[str, str]], **kwargs: Any) -> LLMResponse:
        if not self.api_key and self.provider_name not in ["local", "ollama"]:
            return self._local_fallback(messages)

        try:
            provider = self._get_provider()
            response = provider.chat(messages, **kwargs)
            return LLMResponse(
                content=response.content,
                model=response.model,
                used_remote=True,
                provider=response.provider.value,
                usage=response.usage,
            )
        except Exception as e:
            return self._local_fallback(messages, prefix=f"[LOCAL_BRAIN_ERROR: {str(e)[:50]}]")

    def complete(self, prompt: str, **kwargs: Any) -> LLMResponse:
        return self.chat([{"role": "user", "content": prompt}], **kwargs)

    def count_tokens(self, text: str) -> int:
        try:
            provider = self._get_provider()
            return provider.count_tokens(text)
        except Exception:
            return len(text) // 4

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "LLMBrainClient":
        return cls(
            model=config.get("model", "Pro/deepseek-ai/DeepSeek-V3.2"),
            api_key=config.get("api_key"),
            timeout_sec=config.get("timeout_sec", 45),
            temperature=config.get("temperature", 0.2),
            context_window=config.get("context_window", 8192),
            provider=config.get("provider", "siliconflow"),
            base_url=config.get("base_url"),
        )

    @classmethod
    def get_available_providers(cls) -> List[str]:
        return LLMProviderFactory.available_providers()
