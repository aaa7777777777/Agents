"""
短期记忆（工作记忆）
基于 Redis 实现的即时对话上下文存储
"""

import json
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime

from app.core.base_memory import (
    BaseMemory,
    MemoryType,
    MemoryEntry,
    MemoryQuery,
    MemorySearchResult
)
from app.services.cache import RedisCache, get_cache


class ShortTermMemory(BaseMemory):
    """
    短期记忆实现
    用于存储当前会话的工作记忆，包括：
    - 当前任务状态
    - 中间计算结果
    - 临时变量
    """
    
    def __init__(self, cache: Optional[RedisCache] = None):
        super().__init__(MemoryType.SHORT_TERM)
        self.cache = cache or get_cache()
        self.prefix = "stm:"  # Short-Term Memory
        self.default_ttl = 3600  # 1 小时
    
    def _get_key(self, entry_id: str) -> str:
        """生成存储键"""
        return f"{self.prefix}{entry_id}"
    
    def _get_index_key(self, thread_id: str) -> str:
        """生成索引键"""
        return f"{self.prefix}index:{thread_id}"
    
    async def store(self, entry: MemoryEntry) -> bool:
        """存储记忆条目"""
        try:
            key = self._get_key(entry.id)
            data = entry.to_dict()
            
            # 存储条目
            await self.cache.set_json(key, data, self.default_ttl)
            
            # 更新索引
            if entry.thread_id:
                index_key = self._get_index_key(entry.thread_id)
                await self.cache.sadd(index_key, entry.id)
                await self.cache.expire(index_key, self.default_ttl)
            
            return True
        except Exception as e:
            print(f"Error storing short-term memory: {e}")
            return False
    
    async def retrieve(self, entry_id: str) -> Optional[MemoryEntry]:
        """检索记忆条目"""
        try:
            key = self._get_key(entry_id)
            data = await self.cache.get_json(key)
            
            if data:
                # 更新访问计数
                data["access_count"] = data.get("access_count", 0) + 1
                await self.cache.set_json(key, data, self.default_ttl)
                return MemoryEntry.from_dict(data)
            
            return None
        except Exception as e:
            print(f"Error retrieving short-term memory: {e}")
            return None
    
    async def search(self, query: MemoryQuery) -> MemorySearchResult:
        """搜索记忆条目"""
        import time
        start_time = time.time()
        
        try:
            entries = []
            
            # 如果指定了 thread_id，从索引获取
            if query.thread_id:
                index_key = self._get_index_key(query.thread_id)
                entry_ids = await self.cache.smembers(index_key)
                
                for entry_id in entry_ids:
                    entry = await self.retrieve(entry_id)
                    if entry:
                        # 应用过滤条件
                        if query.min_importance > 0 and entry.importance < query.min_importance:
                            continue
                        if query.query_text and query.query_text.lower() not in entry.content.lower():
                            continue
                        entries.append(entry)
            
            # 按重要性排序
            entries.sort(key=lambda x: x.importance, reverse=True)
            
            # 应用限制
            entries = entries[:query.limit]
            
            return MemorySearchResult(
                entries=entries,
                total_count=len(entries),
                query_time=time.time() - start_time
            )
        except Exception as e:
            print(f"Error searching short-term memory: {e}")
            return MemorySearchResult(entries=[], total_count=0)
    
    async def update(self, entry_id: str, updates: Dict[str, Any]) -> bool:
        """更新记忆条目"""
        try:
            key = self._get_key(entry_id)
            data = await self.cache.get_json(key)
            
            if data:
                data.update(updates)
                data["updated_at"] = datetime.now().isoformat()
                await self.cache.set_json(key, data, self.default_ttl)
                return True
            
            return False
        except Exception as e:
            print(f"Error updating short-term memory: {e}")
            return False
    
    async def delete(self, entry_id: str) -> bool:
        """删除记忆条目"""
        try:
            # 获取条目以获取 thread_id
            entry = await self.retrieve(entry_id)
            
            # 删除条目
            key = self._get_key(entry_id)
            await self.cache.delete(key)
            
            # 从索引中移除
            if entry and entry.thread_id:
                index_key = self._get_index_key(entry.thread_id)
                await self.cache.srem(index_key, entry_id)
            
            return True
        except Exception as e:
            print(f"Error deleting short-term memory: {e}")
            return False
    
    async def clear(
        self,
        user_id: Optional[str] = None,
        thread_id: Optional[str] = None
    ) -> int:
        """清空记忆"""
        try:
            count = 0
            
            if thread_id:
                # 清空特定线程的记忆
                index_key = self._get_index_key(thread_id)
                entry_ids = await self.cache.smembers(index_key)
                
                for entry_id in entry_ids:
                    await self.delete(entry_id)
                    count += 1
                
                await self.cache.delete(index_key)
            else:
                # 清空所有短期记忆
                keys = await self.cache.keys(f"{self.prefix}*")
                for key in keys:
                    await self.cache.delete(key)
                    count += 1
            
            return count
        except Exception as e:
            print(f"Error clearing short-term memory: {e}")
            return 0
    
    # ==================== 便捷方法 ====================
    
    async def set_working_variable(
        self,
        thread_id: str,
        name: str,
        value: Any
    ) -> bool:
        """设置工作变量"""
        entry = MemoryEntry(
            id=f"var:{thread_id}:{name}",
            content=json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value,
            memory_type=self.memory_type,
            thread_id=thread_id,
            metadata={"type": "variable", "name": name},
            importance=0.5
        )
        return await self.store(entry)
    
    async def get_working_variable(
        self,
        thread_id: str,
        name: str,
        default: Any = None
    ) -> Any:
        """获取工作变量"""
        entry_id = f"var:{thread_id}:{name}"
        entry = await self.retrieve(entry_id)
        
        if entry:
            try:
                return json.loads(entry.content)
            except json.JSONDecodeError:
                return entry.content
        
        return default
    
    async def store_task_state(
        self,
        thread_id: str,
        state: Dict[str, Any]
    ) -> bool:
        """存储任务状态"""
        entry = MemoryEntry(
            id=f"state:{thread_id}",
            content=json.dumps(state, ensure_ascii=False),
            memory_type=self.memory_type,
            thread_id=thread_id,
            metadata={"type": "task_state"},
            importance=0.8
        )
        return await self.store(entry)
    
    async def get_task_state(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        entry_id = f"state:{thread_id}"
        entry = await self.retrieve(entry_id)
        
        if entry:
            try:
                return json.loads(entry.content)
            except json.JSONDecodeError:
                return None
        
        return None
