from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union


class LLMProvider(Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    MISTRAL = "mistral"
    SILICONFLOW = "siliconflow"
    OLLAMA = "ollama"
    LOCAL = "local"


@dataclass
class LLMMessage:
    role: str
    content: str
    name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {"role": self.role, "content": self.content}
        if self.name:
            d["name"] = self.name
        return d


@dataclass
class LLMResponse:
    content: str
    model: str
    provider: LLMProvider
    usage: Dict[str, int] = field(default_factory=dict)
    finish_reason: str = "stop"
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.usage.get("total_tokens", 0)


@dataclass
class LLMConfig:
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 60
    context_window: int = 8192
    extra_params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model": self.model,
            "api_key": "***" if self.api_key else None,
            "base_url": self.base_url,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout,
            "context_window": self.context_window,
            "extra_params": self.extra_params,
        }


class BaseLLMProvider(ABC):
    provider: LLMProvider

    @abstractmethod
    def __init__(self, config: LLMConfig) -> None:
        pass

    @abstractmethod
    def chat(
        self,
        messages: List[Union[LLMMessage, Dict[str, str]]],
        **kwargs: Any,
    ) -> LLMResponse:
        pass

    @abstractmethod
    def complete(
        self,
        prompt: str,
        **kwargs: Any,
    ) -> LLMResponse:
        pass

    @abstractmethod
    def healthcheck(self) -> bool:
        pass

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        pass

    def _normalize_messages(
        self,
        messages: List[Union[LLMMessage, Dict[str, str]]],
    ) -> List[LLMMessage]:
        normalized = []
        for msg in messages:
            if isinstance(msg, LLMMessage):
                normalized.append(msg)
            elif isinstance(msg, dict):
                normalized.append(LLMMessage(
                    role=msg.get("role", "user"),
                    content=msg.get("content", ""),
                    name=msg.get("name"),
                ))
        return normalized


class LLMProviderFactory:
    _providers: Dict[LLMProvider, type] = {}

    @classmethod
    def register(cls, provider: LLMProvider, provider_class: type) -> None:
        cls._providers[provider] = provider_class

    @classmethod
    def create(cls, provider: Union[LLMProvider, str], config: LLMConfig) -> BaseLLMProvider:
        if isinstance(provider, str):
            provider = LLMProvider(provider.lower())

        if provider not in cls._providers:
            raise ValueError(f"Unknown provider: {provider}. Available: {list(cls._providers.keys())}")

        return cls._providers[provider](config)

    @classmethod
    def available_providers(cls) -> List[str]:
        return [p.value for p in cls._providers.keys()]


DEFAULT_MODELS: Dict[LLMProvider, List[str]] = {
    LLMProvider.OPENAI: ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
    LLMProvider.ANTHROPIC: ["claude-3-5-sonnet-20241022", "claude-3-opus-20240229", "claude-3-haiku-20240307"],
    LLMProvider.MISTRAL: ["mistral-large-latest", "mistral-medium-latest", "mistral-small-latest"],
    LLMProvider.SILICONFLOW: ["deepseek-ai/DeepSeek-V3", "Qwen/Qwen2.5-72B-Instruct"],
    LLMProvider.OLLAMA: ["llama3", "qwen2", "mistral"],
    LLMProvider.LOCAL: ["fallback"],
}

from cognitive_os.brain.llm_providers.providers import (
    OpenAIProvider,
    AnthropicProvider,
    MistralProvider,
    SiliconFlowProvider,
    OllamaProvider,
    LocalFallbackProvider,
)

__all__ = [
    "LLMProvider",
    "LLMMessage",
    "LLMResponse",
    "LLMConfig",
    "BaseLLMProvider",
    "LLMProviderFactory",
    "DEFAULT_MODELS",
    "OpenAIProvider",
    "AnthropicProvider",
    "MistralProvider",
    "SiliconFlowProvider",
    "OllamaProvider",
    "LocalFallbackProvider",
]
