from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Union

from cognitive_os.brain.llm_providers import (
    BaseLLMProvider,
    LLMConfig,
    LLMMessage,
    LLMProvider,
    LLMResponse,
    LLMProviderFactory,
)


class OpenAIProvider(BaseLLMProvider):
    provider = LLMProvider.OPENAI
    DEFAULT_BASE_URL = "https://api.openai.com/v1"

    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self._client = None
        self._base_url = config.base_url or self.DEFAULT_BASE_URL

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self.config.api_key,
                    base_url=self._base_url,
                    timeout=self.config.timeout,
                )
            except ImportError:
                raise ImportError("openai package not installed. Run: pip install openai")
        return self._client

    def chat(
        self,
        messages: List[Union[LLMMessage, Dict[str, str]]],
        **kwargs: Any,
    ) -> LLMResponse:
        client = self._get_client()
        normalized = self._normalize_messages(messages)

        response = client.chat.completions.create(
            model=kwargs.get("model", self.config.model),
            messages=[m.to_dict() for m in normalized],
            temperature=kwargs.get("temperature", self.config.temperature),
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
            **{k: v for k, v in kwargs.items() if k not in ["model", "temperature", "max_tokens"]},
        )

        return LLMResponse(
            content=response.choices[0].message.content or "",
            model=response.model,
            provider=self.provider,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            finish_reason=response.choices[0].finish_reason,
        )

    def complete(self, prompt: str, **kwargs: Any) -> LLMResponse:
        return self.chat([{"role": "user", "content": prompt}], **kwargs)

    def healthcheck(self) -> bool:
        try:
            client = self._get_client()
            client.models.list()
            return True
        except Exception:
            return False

    def count_tokens(self, text: str) -> int:
        try:
            import tiktoken
            enc = tiktoken.encoding_for_model(self.config.model)
            return len(enc.encode(text))
        except Exception:
            return len(text) // 4


class AnthropicProvider(BaseLLMProvider):
    provider = LLMProvider.ANTHROPIC

    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(
                    api_key=self.config.api_key,
                    timeout=self.config.timeout,
                )
            except ImportError:
                raise ImportError("anthropic package not installed. Run: pip install anthropic")
        return self._client

    def chat(
        self,
        messages: List[Union[LLMMessage, Dict[str, str]]],
        **kwargs: Any,
    ) -> LLMResponse:
        client = self._get_client()
        normalized = self._normalize_messages(messages)

        system_prompt = None
        chat_messages = []
        for msg in normalized:
            if msg.role == "system":
                system_prompt = msg.content
            else:
                chat_messages.append({"role": msg.role, "content": msg.content})

        params = {
            "model": kwargs.get("model", self.config.model),
            "messages": chat_messages,
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
        }
        if system_prompt:
            params["system"] = system_prompt

        response = client.messages.create(**params)

        return LLMResponse(
            content=response.content[0].text,
            model=response.model,
            provider=self.provider,
            usage={
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
            },
            finish_reason=response.stop_reason,
        )

    def complete(self, prompt: str, **kwargs: Any) -> LLMResponse:
        return self.chat([{"role": "user", "content": prompt}], **kwargs)

    def healthcheck(self) -> bool:
        try:
            client = self._get_client()
            client.messages.create(
                model=self.config.model,
                max_tokens=1,
                messages=[{"role": "user", "content": "hi"}],
            )
            return True
        except Exception:
            return False

    def count_tokens(self, text: str) -> int:
        return len(text) // 4


class MistralProvider(BaseLLMProvider):
    provider = LLMProvider.MISTRAL
    DEFAULT_BASE_URL = "https://api.mistral.ai/v1"

    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from mistralai import Mistral
                self._client = Mistral(api_key=self.config.api_key)
            except ImportError:
                raise ImportError("mistralai package not installed. Run: pip install mistralai")
        return self._client

    def chat(
        self,
        messages: List[Union[LLMMessage, Dict[str, str]]],
        **kwargs: Any,
    ) -> LLMResponse:
        client = self._get_client()
        normalized = self._normalize_messages(messages)

        response = client.chat.complete(
            model=kwargs.get("model", self.config.model),
            messages=[m.to_dict() for m in normalized],
            temperature=kwargs.get("temperature", self.config.temperature),
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
        )

        return LLMResponse(
            content=response.choices[0].message.content,
            model=response.model,
            provider=self.provider,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            finish_reason=response.choices[0].finish_reason,
        )

    def complete(self, prompt: str, **kwargs: Any) -> LLMResponse:
        return self.chat([{"role": "user", "content": prompt}], **kwargs)

    def healthcheck(self) -> bool:
        try:
            self.complete("hi", max_tokens=1)
            return True
        except Exception:
            return False

    def count_tokens(self, text: str) -> int:
        return len(text) // 4


class SiliconFlowProvider(BaseLLMProvider):
    provider = LLMProvider.SILICONFLOW
    DEFAULT_BASE_URL = "https://api.siliconflow.cn/v1"

    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self._client = None
        self._base_url = config.base_url or self.DEFAULT_BASE_URL

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self.config.api_key,
                    base_url=self._base_url,
                    timeout=self.config.timeout,
                )
            except ImportError:
                raise ImportError("openai package not installed. Run: pip install openai")
        return self._client

    def chat(
        self,
        messages: List[Union[LLMMessage, Dict[str, str]]],
        **kwargs: Any,
    ) -> LLMResponse:
        client = self._get_client()
        normalized = self._normalize_messages(messages)

        response = client.chat.completions.create(
            model=kwargs.get("model", self.config.model),
            messages=[m.to_dict() for m in normalized],
            temperature=kwargs.get("temperature", self.config.temperature),
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
        )

        return LLMResponse(
            content=response.choices[0].message.content or "",
            model=response.model,
            provider=self.provider,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            finish_reason=response.choices[0].finish_reason,
        )

    def complete(self, prompt: str, **kwargs: Any) -> LLMResponse:
        return self.chat([{"role": "user", "content": prompt}], **kwargs)

    def healthcheck(self) -> bool:
        try:
            client = self._get_client()
            client.models.list()
            return True
        except Exception:
            return False

    def count_tokens(self, text: str) -> int:
        return len(text) // 4


class OllamaProvider(BaseLLMProvider):
    provider = LLMProvider.OLLAMA
    DEFAULT_BASE_URL = "http://localhost:11434"

    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self._base_url = config.base_url or self.DEFAULT_BASE_URL

    def chat(
        self,
        messages: List[Union[LLMMessage, Dict[str, str]]],
        **kwargs: Any,
    ) -> LLMResponse:
        import urllib.request
        import urllib.error

        normalized = self._normalize_messages(messages)

        data = {
            "model": kwargs.get("model", self.config.model),
            "messages": [m.to_dict() for m in normalized],
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", self.config.temperature),
                "num_predict": kwargs.get("max_tokens", self.config.max_tokens),
            },
        }

        req = urllib.request.Request(
            f"{self._base_url}/api/chat",
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as e:
            raise ConnectionError(f"Ollama connection failed: {e}")

        return LLMResponse(
            content=result.get("message", {}).get("content", ""),
            model=result.get("model", self.config.model),
            provider=self.provider,
            usage={
                "prompt_tokens": result.get("prompt_eval_count", 0),
                "completion_tokens": result.get("eval_count", 0),
                "total_tokens": result.get("prompt_eval_count", 0) + result.get("eval_count", 0),
            },
            finish_reason="stop",
        )

    def complete(self, prompt: str, **kwargs: Any) -> LLMResponse:
        return self.chat([{"role": "user", "content": prompt}], **kwargs)

    def healthcheck(self) -> bool:
        import urllib.request
        import urllib.error
        try:
            req = urllib.request.Request(f"{self._base_url}/api/tags")
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status == 200
        except Exception:
            return False

    def count_tokens(self, text: str) -> int:
        return len(text) // 4


class LocalFallbackProvider(BaseLLMProvider):
    provider = LLMProvider.LOCAL

    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    def chat(
        self,
        messages: List[Union[LLMMessage, Dict[str, str]]],
        **kwargs: Any,
    ) -> LLMResponse:
        normalized = self._normalize_messages(messages)
        last_user_msg = ""
        for msg in reversed(normalized):
            if msg.role == "user":
                last_user_msg = msg.content
                break

        response_content = self._generate_deterministic_response(last_user_msg)

        return LLMResponse(
            content=response_content,
            model="local-fallback",
            provider=self.provider,
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            finish_reason="stop",
            metadata={"fallback": True},
        )

    def complete(self, prompt: str, **kwargs: Any) -> LLMResponse:
        return self.chat([{"role": "user", "content": prompt}], **kwargs)

    def healthcheck(self) -> bool:
        return True

    def count_tokens(self, text: str) -> int:
        return len(text) // 4

    def _generate_deterministic_response(self, query: str) -> str:
        keywords = ["建议", "决策", "下一步", "策略", "方案", "总结"]
        if any(k in query for k in keywords):
            return (
                "【本地回退模式】\n"
                "1. 结论: 基于现有知识库分析，建议进一步收集信息。\n"
                "2. 依据: 当前查询触发了认知循环，但本地模式无法进行深度推理。\n"
                "3. 风险提示: 本地回退模式功能有限，建议配置远程LLM以获得更好体验。\n"
                "4. 下一步行动: 配置SILICONFLOW_API_KEY或其他LLM提供商的API密钥。"
            )
        return (
            "【本地回退模式】\n"
            "当前处于本地回退模式，无法提供智能回答。\n"
            "请配置远程LLM API密钥以获得完整功能。\n"
            f"您的问题: {query[:100]}..."
        )


LLMProviderFactory.register(LLMProvider.OPENAI, OpenAIProvider)
LLMProviderFactory.register(LLMProvider.ANTHROPIC, AnthropicProvider)
LLMProviderFactory.register(LLMProvider.MISTRAL, MistralProvider)
LLMProviderFactory.register(LLMProvider.SILICONFLOW, SiliconFlowProvider)
LLMProviderFactory.register(LLMProvider.OLLAMA, OllamaProvider)
LLMProviderFactory.register(LLMProvider.LOCAL, LocalFallbackProvider)
