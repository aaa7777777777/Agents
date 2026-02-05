"""
Memory 抽象基类
定义所有记忆存储的通用接口
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class MemoryType(str, Enum):
    """记忆类型枚举"""
    SHORT_TERM = "short_term"  # 短期记忆（工作记忆）
    LONG_TERM = "long_term"  # 长期记忆（用户档案）
    EPISODIC = "episodic"  # 情景记忆（对话历史）
    SEMANTIC = "semantic"  # 语义记忆（知识库）


@dataclass
class MemoryEntry:
    """记忆条目"""
    id: str
    content: str
    memory_type: MemoryType
    user_id: Optional[str] = None
    thread_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    importance: float = 0.5  # 重要性评分 0-1
    access_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type.value,
            "user_id": self.user_id,
            "thread_id": self.thread_id,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "importance": self.importance,
            "access_count": self.access_count
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEntry":
        """从字典创建"""
        data = data.copy()
        data["memory_type"] = MemoryType(data["memory_type"])
        if data.get("created_at"):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if data.get("updated_at"):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        if data.get("expires_at"):
            data["expires_at"] = datetime.fromisoformat(data["expires_at"])
        return cls(**data)


@dataclass
class MemoryQuery:
    """记忆查询条件"""
    query_text: Optional[str] = None
    user_id: Optional[str] = None
    thread_id: Optional[str] = None
    memory_type: Optional[MemoryType] = None
    min_importance: float = 0.0
    limit: int = 10
    include_expired: bool = False
    metadata_filters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MemorySearchResult:
    """记忆搜索结果"""
    entries: List[MemoryEntry]
    total_count: int
    query_time: float = 0.0
    
    def get_contents(self) -> List[str]:
        """获取所有内容"""
        return [entry.content for entry in self.entries]
    
    def get_formatted(self, separator: str = "\n---\n") -> str:
        """获取格式化的内容"""
        return separator.join(self.get_contents())


class BaseMemory(ABC):
    """
    Memory 抽象基类
    所有具体记忆存储都必须继承此类并实现抽象方法
    """
    
    def __init__(self, memory_type: MemoryType):
        self.memory_type = memory_type
    
    @abstractmethod
    async def store(self, entry: MemoryEntry) -> bool:
        """
        存储记忆条目
        
        Args:
            entry: 记忆条目
            
        Returns:
            bool: 是否存储成功
        """
        pass
    
    @abstractmethod
    async def retrieve(self, entry_id: str) -> Optional[MemoryEntry]:
        """
        根据 ID 检索记忆条目
        
        Args:
            entry_id: 条目 ID
            
        Returns:
            Optional[MemoryEntry]: 记忆条目，不存在则返回 None
        """
        pass
    
    @abstractmethod
    async def search(self, query: MemoryQuery) -> MemorySearchResult:
        """
        搜索记忆条目
        
        Args:
            query: 查询条件
            
        Returns:
            MemorySearchResult: 搜索结果
        """
        pass
    
    @abstractmethod
    async def update(self, entry_id: str, updates: Dict[str, Any]) -> bool:
        """
        更新记忆条目
        
        Args:
            entry_id: 条目 ID
            updates: 更新内容
            
        Returns:
            bool: 是否更新成功
        """
        pass
    
    @abstractmethod
    async def delete(self, entry_id: str) -> bool:
        """
        删除记忆条目
        
        Args:
            entry_id: 条目 ID
            
        Returns:
            bool: 是否删除成功
        """
        pass
    
    @abstractmethod
    async def clear(self, user_id: Optional[str] = None, thread_id: Optional[str] = None) -> int:
        """
        清空记忆
        
        Args:
            user_id: 用户 ID（可选，指定则只清空该用户的记忆）
            thread_id: 线程 ID（可选，指定则只清空该线程的记忆）
            
        Returns:
            int: 清空的条目数量
        """
        pass
    
    async def store_text(
        self,
        content: str,
        user_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        importance: float = 0.5
    ) -> bool:
        """
        便捷方法：存储文本内容
        """
        import uuid
        entry = MemoryEntry(
            id=str(uuid.uuid4()),
            content=content,
            memory_type=self.memory_type,
            user_id=user_id,
            thread_id=thread_id,
            metadata=metadata or {},
            importance=importance
        )
        return await self.store(entry)
    
    async def search_text(
        self,
        query_text: str,
        user_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        limit: int = 10
    ) -> List[str]:
        """
        便捷方法：搜索文本内容
        """
        query = MemoryQuery(
            query_text=query_text,
            user_id=user_id,
            thread_id=thread_id,
            memory_type=self.memory_type,
            limit=limit
        )
        result = await self.search(query)
        return result.get_contents()
