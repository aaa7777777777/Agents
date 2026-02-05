"""
Redis 缓存客户端
提供短期记忆存储和会话管理
"""

import json
import asyncio
from typing import Any, Dict, List, Optional, Union
from datetime import timedelta

from app.config import settings


class RedisCache:
    """Redis 缓存客户端"""
    
    _instance: Optional["RedisCache"] = None
    
    def __new__(cls, *args, **kwargs):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        
        self._initialized = True
        self._client = None
        self._pool = None
    
    async def _get_client(self):
        """获取 Redis 客户端"""
        if self._client is None:
            import redis.asyncio as redis
            
            self._pool = redis.ConnectionPool.from_url(
                settings.redis_url,
                max_connections=10,
                decode_responses=True
            )
            self._client = redis.Redis(connection_pool=self._pool)
        return self._client
    
    async def get(self, key: str) -> Optional[str]:
        """获取值"""
        client = await self._get_client()
        return await client.get(key)
    
    async def set(
        self,
        key: str,
        value: str,
        ttl: Optional[int] = None
    ) -> bool:
        """设置值"""
        client = await self._get_client()
        ttl = ttl or settings.REDIS_TTL
        return await client.set(key, value, ex=ttl)
    
    async def delete(self, key: str) -> bool:
        """删除键"""
        client = await self._get_client()
        return await client.delete(key) > 0
    
    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        client = await self._get_client()
        return await client.exists(key) > 0
    
    async def expire(self, key: str, ttl: int) -> bool:
        """设置过期时间"""
        client = await self._get_client()
        return await client.expire(key, ttl)
    
    async def ttl(self, key: str) -> int:
        """获取剩余过期时间"""
        client = await self._get_client()
        return await client.ttl(key)
    
    # ==================== JSON 操作 ====================
    
    async def get_json(self, key: str) -> Optional[Any]:
        """获取 JSON 值"""
        value = await self.get(key)
        if value:
            return json.loads(value)
        return None
    
    async def set_json(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """设置 JSON 值"""
        return await self.set(key, json.dumps(value, ensure_ascii=False), ttl)
    
    # ==================== 列表操作 ====================
    
    async def lpush(self, key: str, *values: str) -> int:
        """从左侧推入列表"""
        client = await self._get_client()
        return await client.lpush(key, *values)
    
    async def rpush(self, key: str, *values: str) -> int:
        """从右侧推入列表"""
        client = await self._get_client()
        return await client.rpush(key, *values)
    
    async def lpop(self, key: str) -> Optional[str]:
        """从左侧弹出"""
        client = await self._get_client()
        return await client.lpop(key)
    
    async def rpop(self, key: str) -> Optional[str]:
        """从右侧弹出"""
        client = await self._get_client()
        return await client.rpop(key)
    
    async def lrange(self, key: str, start: int, end: int) -> List[str]:
        """获取列表范围"""
        client = await self._get_client()
        return await client.lrange(key, start, end)
    
    async def llen(self, key: str) -> int:
        """获取列表长度"""
        client = await self._get_client()
        return await client.llen(key)
    
    async def ltrim(self, key: str, start: int, end: int) -> bool:
        """裁剪列表"""
        client = await self._get_client()
        return await client.ltrim(key, start, end)
    
    # ==================== 哈希操作 ====================
    
    async def hget(self, key: str, field: str) -> Optional[str]:
        """获取哈希字段"""
        client = await self._get_client()
        return await client.hget(key, field)
    
    async def hset(self, key: str, field: str, value: str) -> bool:
        """设置哈希字段"""
        client = await self._get_client()
        return await client.hset(key, field, value)
    
    async def hmset(self, key: str, mapping: Dict[str, str]) -> bool:
        """批量设置哈希字段"""
        client = await self._get_client()
        return await client.hset(key, mapping=mapping)
    
    async def hgetall(self, key: str) -> Dict[str, str]:
        """获取所有哈希字段"""
        client = await self._get_client()
        return await client.hgetall(key)
    
    async def hdel(self, key: str, *fields: str) -> int:
        """删除哈希字段"""
        client = await self._get_client()
        return await client.hdel(key, *fields)
    
    async def hexists(self, key: str, field: str) -> bool:
        """检查哈希字段是否存在"""
        client = await self._get_client()
        return await client.hexists(key, field)
    
    # ==================== 集合操作 ====================
    
    async def sadd(self, key: str, *values: str) -> int:
        """添加集合成员"""
        client = await self._get_client()
        return await client.sadd(key, *values)
    
    async def srem(self, key: str, *values: str) -> int:
        """移除集合成员"""
        client = await self._get_client()
        return await client.srem(key, *values)
    
    async def smembers(self, key: str) -> set:
        """获取所有集合成员"""
        client = await self._get_client()
        return await client.smembers(key)
    
    async def sismember(self, key: str, value: str) -> bool:
        """检查是否是集合成员"""
        client = await self._get_client()
        return await client.sismember(key, value)
    
    # ==================== 通用操作 ====================
    
    async def keys(self, pattern: str = "*") -> List[str]:
        """获取匹配的键"""
        client = await self._get_client()
        return await client.keys(pattern)
    
    async def delete_pattern(self, pattern: str) -> int:
        """删除匹配的键"""
        client = await self._get_client()
        keys = await self.keys(pattern)
        if keys:
            return await client.delete(*keys)
        return 0
    
    async def incr(self, key: str) -> int:
        """自增"""
        client = await self._get_client()
        return await client.incr(key)
    
    async def decr(self, key: str) -> int:
        """自减"""
        client = await self._get_client()
        return await client.decr(key)
    
    async def close(self):
        """关闭连接"""
        if self._client:
            await self._client.close()
            self._client = None
        if self._pool:
            await self._pool.disconnect()
            self._pool = None


class SessionManager:
    """会话管理器"""
    
    def __init__(self, cache: Optional[RedisCache] = None):
        self.cache = cache or RedisCache()
        self.prefix = "session:"
        self.default_ttl = 3600 * 24  # 24 小时
    
    def _get_key(self, session_id: str) -> str:
        """生成会话键"""
        return f"{self.prefix}{session_id}"
    
    async def create_session(
        self,
        session_id: str,
        data: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """创建会话"""
        key = self._get_key(session_id)
        return await self.cache.set_json(key, data, ttl or self.default_ttl)
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话"""
        key = self._get_key(session_id)
        return await self.cache.get_json(key)
    
    async def update_session(
        self,
        session_id: str,
        data: Dict[str, Any]
    ) -> bool:
        """更新会话"""
        key = self._get_key(session_id)
        existing = await self.cache.get_json(key)
        if existing:
            existing.update(data)
            ttl = await self.cache.ttl(key)
            return await self.cache.set_json(key, existing, ttl if ttl > 0 else self.default_ttl)
        return False
    
    async def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        key = self._get_key(session_id)
        return await self.cache.delete(key)
    
    async def extend_session(self, session_id: str, ttl: Optional[int] = None) -> bool:
        """延长会话有效期"""
        key = self._get_key(session_id)
        return await self.cache.expire(key, ttl or self.default_ttl)


class ConversationHistory:
    """对话历史管理"""
    
    def __init__(self, cache: Optional[RedisCache] = None):
        self.cache = cache or RedisCache()
        self.prefix = "conversation:"
        self.max_messages = 50  # 最大消息数
        self.default_ttl = 3600 * 2  # 2 小时
    
    def _get_key(self, thread_id: str) -> str:
        """生成对话键"""
        return f"{self.prefix}{thread_id}"
    
    async def add_message(
        self,
        thread_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict] = None
    ) -> bool:
        """添加消息"""
        key = self._get_key(thread_id)
        message = json.dumps({
            "role": role,
            "content": content,
            "metadata": metadata or {}
        }, ensure_ascii=False)
        
        await self.cache.rpush(key, message)
        await self.cache.ltrim(key, -self.max_messages, -1)
        await self.cache.expire(key, self.default_ttl)
        return True
    
    async def get_messages(
        self,
        thread_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """获取消息历史"""
        key = self._get_key(thread_id)
        limit = limit or self.max_messages
        
        messages = await self.cache.lrange(key, -limit, -1)
        return [json.loads(m) for m in messages]
    
    async def clear_history(self, thread_id: str) -> bool:
        """清空对话历史"""
        key = self._get_key(thread_id)
        return await self.cache.delete(key)
    
    async def get_formatted_history(
        self,
        thread_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """获取格式化的消息历史（用于 LLM）"""
        messages = await self.get_messages(thread_id, limit)
        return [
            {"role": m["role"], "content": m["content"]}
            for m in messages
        ]


# 便捷函数
def get_cache() -> RedisCache:
    """获取缓存实例"""
    return RedisCache()


def get_session_manager() -> SessionManager:
    """获取会话管理器"""
    return SessionManager()


def get_conversation_history() -> ConversationHistory:
    """获取对话历史管理器"""
    return ConversationHistory()
