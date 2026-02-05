"""
LLM 推理引擎适配层
支持 Ollama 和 vLLM 两种后端
"""

import asyncio
import httpx
import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum

from app.config import settings


class LLMProvider(str, Enum):
    """LLM 提供商枚举"""
    OLLAMA = "ollama"
    VLLM = "vllm"
    OPENAI = "openai"


@dataclass
class LLMMessage:
    """LLM 消息结构"""
    role: str  # system, user, assistant, tool
    content: str
    name: Optional[str] = None
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None


@dataclass
class LLMResponse:
    """LLM 响应结构"""
    content: str
    role: str = "assistant"
    tool_calls: Optional[List[Dict]] = None
    finish_reason: Optional[str] = None
    usage: Dict[str, int] = field(default_factory=dict)
    raw_response: Optional[Dict] = None


@dataclass
class LLMConfig:
    """LLM 配置"""
    model: str = settings.LLM_MODEL
    temperature: float = settings.LLM_TEMPERATURE
    max_tokens: int = settings.LLM_MAX_TOKENS
    top_p: float = 0.9
    stop: Optional[List[str]] = None
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.0


class BaseLLMEngine(ABC):
    """LLM 引擎抽象基类"""
    
    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()
    
    @abstractmethod
    async def chat(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[Dict]] = None,
        **kwargs
    ) -> LLMResponse:
        """
        聊天补全
        
        Args:
            messages: 消息列表
            tools: 工具定义列表（可选）
            **kwargs: 其他参数
            
        Returns:
            LLMResponse: LLM 响应
        """
        pass
    
    @abstractmethod
    async def chat_stream(
        self,
        messages: List[LLMMessage],
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        流式聊天补全
        
        Args:
            messages: 消息列表
            **kwargs: 其他参数
            
        Yields:
            str: 响应文本片段
        """
        pass
    
    async def generate(self, prompt: str, **kwargs) -> str:
        """
        简单文本生成
        
        Args:
            prompt: 提示词
            **kwargs: 其他参数
            
        Returns:
            str: 生成的文本
        """
        messages = [LLMMessage(role="user", content=prompt)]
        response = await self.chat(messages, **kwargs)
        return response.content


class OllamaEngine(BaseLLMEngine):
    """Ollama LLM 引擎"""
    
    def __init__(self, config: Optional[LLMConfig] = None, base_url: Optional[str] = None):
        super().__init__(config)
        self.base_url = base_url or settings.LLM_BASE_URL
        self.client = httpx.AsyncClient(timeout=settings.LLM_TIMEOUT)
    
    async def chat(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[Dict]] = None,
        **kwargs
    ) -> LLMResponse:
        """Ollama 聊天补全"""
        
        # 构建请求体
        payload = {
            "model": kwargs.get("model", self.config.model),
            "messages": [
                {"role": m.role, "content": m.content}
                for m in messages
            ],
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", self.config.temperature),
                "num_predict": kwargs.get("max_tokens", self.config.max_tokens),
                "top_p": kwargs.get("top_p", self.config.top_p),
            }
        }
        
        # 添加工具（如果支持）
        if tools:
            payload["tools"] = tools
        
        # 发送请求
        response = await self.client.post(
            f"{self.base_url}/api/chat",
            json=payload
        )
        response.raise_for_status()
        
        data = response.json()
        
        return LLMResponse(
            content=data.get("message", {}).get("content", ""),
            role="assistant",
            tool_calls=data.get("message", {}).get("tool_calls"),
            finish_reason=data.get("done_reason"),
            usage={
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
                "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0)
            },
            raw_response=data
        )
    
    async def chat_stream(
        self,
        messages: List[LLMMessage],
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Ollama 流式聊天补全"""
        
        payload = {
            "model": kwargs.get("model", self.config.model),
            "messages": [
                {"role": m.role, "content": m.content}
                for m in messages
            ],
            "stream": True,
            "options": {
                "temperature": kwargs.get("temperature", self.config.temperature),
                "num_predict": kwargs.get("max_tokens", self.config.max_tokens),
            }
        }
        
        async with self.client.stream(
            "POST",
            f"{self.base_url}/api/chat",
            json=payload
        ) as response:
            async for line in response.aiter_lines():
                if line:
                    data = json.loads(line)
                    content = data.get("message", {}).get("content", "")
                    if content:
                        yield content
    
    async def close(self):
        """关闭客户端"""
        await self.client.aclose()


class VLLMEngine(BaseLLMEngine):
    """vLLM LLM 引擎（OpenAI 兼容接口）"""
    
    def __init__(self, config: Optional[LLMConfig] = None, base_url: Optional[str] = None):
        super().__init__(config)
        self.base_url = base_url or settings.LLM_BASE_URL
        self.api_key = settings.LLM_API_KEY or "EMPTY"
        self.client = httpx.AsyncClient(timeout=settings.LLM_TIMEOUT)
    
    async def chat(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[Dict]] = None,
        **kwargs
    ) -> LLMResponse:
        """vLLM 聊天补全（OpenAI 兼容）"""
        
        payload = {
            "model": kwargs.get("model", self.config.model),
            "messages": [
                {"role": m.role, "content": m.content}
                for m in messages
            ],
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "top_p": kwargs.get("top_p", self.config.top_p),
            "stream": False
        }
        
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = kwargs.get("tool_choice", "auto")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        response = await self.client.post(
            f"{self.base_url}/v1/chat/completions",
            json=payload,
            headers=headers
        )
        response.raise_for_status()
        
        data = response.json()
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        
        return LLMResponse(
            content=message.get("content", ""),
            role=message.get("role", "assistant"),
            tool_calls=message.get("tool_calls"),
            finish_reason=choice.get("finish_reason"),
            usage=data.get("usage", {}),
            raw_response=data
        )
    
    async def chat_stream(
        self,
        messages: List[LLMMessage],
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """vLLM 流式聊天补全"""
        
        payload = {
            "model": kwargs.get("model", self.config.model),
            "messages": [
                {"role": m.role, "content": m.content}
                for m in messages
            ],
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "stream": True
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        async with self.client.stream(
            "POST",
            f"{self.base_url}/v1/chat/completions",
            json=payload,
            headers=headers
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    data = json.loads(data_str)
                    delta = data.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield content
    
    async def close(self):
        """关闭客户端"""
        await self.client.aclose()


class LLMEngineFactory:
    """LLM 引擎工厂"""
    
    _engines: Dict[str, BaseLLMEngine] = {}
    
    @classmethod
    def get_engine(
        cls,
        provider: Optional[str] = None,
        config: Optional[LLMConfig] = None
    ) -> BaseLLMEngine:
        """
        获取 LLM 引擎实例
        
        Args:
            provider: 提供商名称
            config: LLM 配置
            
        Returns:
            BaseLLMEngine: LLM 引擎实例
        """
        provider = provider or settings.LLM_PROVIDER
        
        cache_key = f"{provider}_{config.model if config else 'default'}"
        
        if cache_key not in cls._engines:
            if provider == LLMProvider.OLLAMA.value:
                cls._engines[cache_key] = OllamaEngine(config)
            elif provider in [LLMProvider.VLLM.value, LLMProvider.OPENAI.value]:
                cls._engines[cache_key] = VLLMEngine(config)
            else:
                raise ValueError(f"Unsupported LLM provider: {provider}")
        
        return cls._engines[cache_key]
    
    @classmethod
    async def close_all(cls):
        """关闭所有引擎"""
        for engine in cls._engines.values():
            await engine.close()
        cls._engines.clear()


# 便捷函数
def get_llm_engine(provider: Optional[str] = None) -> BaseLLMEngine:
    """获取默认 LLM 引擎"""
    return LLMEngineFactory.get_engine(provider)
