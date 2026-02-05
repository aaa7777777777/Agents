"""
统一记忆管理器
整合短期、长期和语义记忆，提供统一的记忆操作接口
"""

import uuid
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from dataclasses import dataclass, field

from app.core.base_memory import (
    MemoryType,
    MemoryEntry,
    MemoryQuery,
    MemorySearchResult
)
from app.memory.short_term import ShortTermMemory
from app.memory.long_term import LongTermMemory, UserProfile
from app.memory.semantic import SemanticMemory


@dataclass
class UnifiedMemoryResult:
    """统一记忆查询结果"""
    short_term: MemorySearchResult
    long_term: MemorySearchResult
    semantic: MemorySearchResult
    total_count: int = 0
    query_time: float = 0.0
    
    def get_all_entries(self) -> List[MemoryEntry]:
        """获取所有记忆条目"""
        entries = []
        entries.extend(self.short_term.entries)
        entries.extend(self.long_term.entries)
        entries.extend(self.semantic.entries)
        return entries
    
    def get_all_contents(self) -> List[str]:
        """获取所有内容"""
        return [entry.content for entry in self.get_all_entries()]
    
    def get_formatted_context(self, max_length: int = 2000) -> str:
        """获取格式化的上下文"""
        parts = []
        total_length = 0
        
        # 优先添加短期记忆
        if self.short_term.entries:
            stm_content = "【工作记忆】\n" + "\n".join(
                e.content for e in self.short_term.entries[:3]
            )
            if total_length + len(stm_content) < max_length:
                parts.append(stm_content)
                total_length += len(stm_content)
        
        # 添加语义记忆
        if self.semantic.entries:
            sem_content = "【相关知识】\n" + "\n".join(
                e.content for e in self.semantic.entries[:3]
            )
            if total_length + len(sem_content) < max_length:
                parts.append(sem_content)
                total_length += len(sem_content)
        
        # 添加长期记忆
        if self.long_term.entries:
            ltm_content = "【历史记录】\n" + "\n".join(
                e.content for e in self.long_term.entries[:2]
            )
            if total_length + len(ltm_content) < max_length:
                parts.append(ltm_content)
        
        return "\n\n".join(parts)


class MemoryManager:
    """
    统一记忆管理器
    协调多层记忆系统的存储和检索
    """
    
    _instance: Optional["MemoryManager"] = None
    
    def __new__(cls, *args, **kwargs):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        
        self._initialized = True
        self.short_term = ShortTermMemory()
        self.long_term = LongTermMemory()
        self.semantic = SemanticMemory()
    
    # ==================== 统一存储接口 ====================
    
    async def store(
        self,
        content: str,
        memory_type: MemoryType,
        user_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        importance: float = 0.5
    ) -> bool:
        """
        存储记忆到指定类型的存储
        
        Args:
            content: 记忆内容
            memory_type: 记忆类型
            user_id: 用户 ID
            thread_id: 线程 ID
            metadata: 元数据
            importance: 重要性评分
            
        Returns:
            bool: 是否存储成功
        """
        entry = MemoryEntry(
            id=str(uuid.uuid4()),
            content=content,
            memory_type=memory_type,
            user_id=user_id,
            thread_id=thread_id,
            metadata=metadata or {},
            importance=importance
        )
        
        if memory_type == MemoryType.SHORT_TERM:
            return await self.short_term.store(entry)
        elif memory_type == MemoryType.LONG_TERM:
            return await self.long_term.store(entry)
        elif memory_type == MemoryType.SEMANTIC:
            return await self.semantic.store(entry)
        else:
            # 默认存储到短期记忆
            return await self.short_term.store(entry)
    
    async def store_to_all(
        self,
        content: str,
        user_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        importance: float = 0.5
    ) -> Dict[str, bool]:
        """
        存储记忆到所有存储层
        
        Returns:
            Dict[str, bool]: 各层存储结果
        """
        results = {}
        
        for memory_type in [MemoryType.SHORT_TERM, MemoryType.LONG_TERM, MemoryType.SEMANTIC]:
            results[memory_type.value] = await self.store(
                content=content,
                memory_type=memory_type,
                user_id=user_id,
                thread_id=thread_id,
                metadata=metadata,
                importance=importance
            )
        
        return results
    
    # ==================== 统一检索接口 ====================
    
    async def search(
        self,
        query_text: str,
        user_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        memory_types: Optional[List[MemoryType]] = None,
        limit: int = 10,
        min_importance: float = 0.0
    ) -> UnifiedMemoryResult:
        """
        在多层记忆中搜索
        
        Args:
            query_text: 查询文本
            user_id: 用户 ID
            thread_id: 线程 ID
            memory_types: 要搜索的记忆类型列表
            limit: 每层返回的最大数量
            min_importance: 最小重要性
            
        Returns:
            UnifiedMemoryResult: 统一搜索结果
        """
        import time
        start_time = time.time()
        
        # 默认搜索所有类型
        if memory_types is None:
            memory_types = [MemoryType.SHORT_TERM, MemoryType.LONG_TERM, MemoryType.SEMANTIC]
        
        query = MemoryQuery(
            query_text=query_text,
            user_id=user_id,
            thread_id=thread_id,
            limit=limit,
            min_importance=min_importance
        )
        
        # 并行搜索各层
        stm_result = MemorySearchResult(entries=[], total_count=0)
        ltm_result = MemorySearchResult(entries=[], total_count=0)
        sem_result = MemorySearchResult(entries=[], total_count=0)
        
        if MemoryType.SHORT_TERM in memory_types:
            stm_result = await self.short_term.search(query)
        
        if MemoryType.LONG_TERM in memory_types:
            ltm_result = await self.long_term.search(query)
        
        if MemoryType.SEMANTIC in memory_types:
            sem_result = await self.semantic.search(query)
        
        total_count = stm_result.total_count + ltm_result.total_count + sem_result.total_count
        
        return UnifiedMemoryResult(
            short_term=stm_result,
            long_term=ltm_result,
            semantic=sem_result,
            total_count=total_count,
            query_time=time.time() - start_time
        )
    
    async def get_context(
        self,
        query_text: str,
        user_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        max_length: int = 2000
    ) -> str:
        """
        获取查询相关的上下文
        用于增强 LLM 生成
        
        Args:
            query_text: 查询文本
            user_id: 用户 ID
            thread_id: 线程 ID
            max_length: 最大上下文长度
            
        Returns:
            str: 格式化的上下文
        """
        result = await self.search(
            query_text=query_text,
            user_id=user_id,
            thread_id=thread_id,
            limit=5
        )
        
        return result.get_formatted_context(max_length)
    
    # ==================== 用户档案管理 ====================
    
    async def get_user_profile(self, user_id: str) -> Optional[UserProfile]:
        """获取用户档案"""
        return await self.long_term.get_user_profile(user_id)
    
    async def save_user_profile(self, profile: UserProfile) -> bool:
        """保存用户档案"""
        return await self.long_term.save_user_profile(profile)
    
    async def update_user_preferences(
        self,
        user_id: str,
        preferences: Dict[str, Any]
    ) -> bool:
        """更新用户偏好"""
        return await self.long_term.update_user_preferences(user_id, preferences)
    
    # ==================== 工作记忆管理 ====================
    
    async def set_working_variable(
        self,
        thread_id: str,
        name: str,
        value: Any
    ) -> bool:
        """设置工作变量"""
        return await self.short_term.set_working_variable(thread_id, name, value)
    
    async def get_working_variable(
        self,
        thread_id: str,
        name: str,
        default: Any = None
    ) -> Any:
        """获取工作变量"""
        return await self.short_term.get_working_variable(thread_id, name, default)
    
    async def store_task_state(
        self,
        thread_id: str,
        state: Dict[str, Any]
    ) -> bool:
        """存储任务状态"""
        return await self.short_term.store_task_state(thread_id, state)
    
    async def get_task_state(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        return await self.short_term.get_task_state(thread_id)
    
    # ==================== 知识库管理 ====================
    
    async def add_knowledge(
        self,
        content: str,
        source: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        importance: float = 0.5
    ) -> bool:
        """添加知识条目"""
        return await self.semantic.add_knowledge(
            content=content,
            source=source,
            category=category,
            tags=tags,
            importance=importance
        )
    
    async def search_knowledge(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """搜索知识库"""
        return await self.semantic.search_knowledge(
            query=query,
            category=category,
            limit=limit
        )
    
    # ==================== 清理操作 ====================
    
    async def clear_thread_memory(self, thread_id: str) -> Dict[str, int]:
        """清空线程相关的所有记忆"""
        results = {}
        results["short_term"] = await self.short_term.clear(thread_id=thread_id)
        results["long_term"] = await self.long_term.clear(thread_id=thread_id)
        return results
    
    async def clear_user_memory(self, user_id: str) -> Dict[str, int]:
        """清空用户相关的所有记忆"""
        results = {}
        results["short_term"] = await self.short_term.clear(user_id=user_id)
        results["long_term"] = await self.long_term.clear(user_id=user_id)
        return results


# 便捷函数
def get_memory_manager() -> MemoryManager:
    """获取记忆管理器单例"""
    return MemoryManager()
