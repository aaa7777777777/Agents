"""
长期记忆（用户档案）
基于 PostgreSQL 实现的持久化用户偏好存储
"""

import json
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field

from app.core.base_memory import (
    BaseMemory,
    MemoryType,
    MemoryEntry,
    MemoryQuery,
    MemorySearchResult
)
from app.config import settings


@dataclass
class UserProfile:
    """用户档案"""
    user_id: str
    preferences: Dict[str, Any] = field(default_factory=dict)
    interests: List[str] = field(default_factory=list)
    writing_style: Optional[str] = None
    tone_preference: Optional[str] = None
    niche: Optional[str] = None
    constraints: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "user_id": self.user_id,
            "preferences": self.preferences,
            "interests": self.interests,
            "writing_style": self.writing_style,
            "tone_preference": self.tone_preference,
            "niche": self.niche,
            "constraints": self.constraints,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserProfile":
        """从字典创建"""
        data = data.copy()
        if data.get("created_at"):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if data.get("updated_at"):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        return cls(**data)


class LongTermMemory(BaseMemory):
    """
    长期记忆实现
    用于存储持久化的用户信息，包括：
    - 用户偏好设置
    - 历史行为模式
    - 个性化配置
    """
    
    def __init__(self):
        super().__init__(MemoryType.LONG_TERM)
        self._engine = None
        self._session_factory = None
        self._initialized = False
    
    async def _ensure_initialized(self):
        """确保数据库已初始化"""
        if self._initialized:
            return
        
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy import text
        
        self._engine = create_async_engine(
            settings.postgres_async_url,
            echo=settings.DEBUG,
            pool_size=5,
            max_overflow=10
        )
        
        self._session_factory = sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        # 创建表
        async with self._engine.begin() as conn:
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS long_term_memory (
                    id VARCHAR(255) PRIMARY KEY,
                    content TEXT NOT NULL,
                    user_id VARCHAR(255),
                    thread_id VARCHAR(255),
                    memory_type VARCHAR(50) NOT NULL,
                    importance FLOAT DEFAULT 0.5,
                    access_count INTEGER DEFAULT 0,
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP
                )
            """))
            
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_ltm_user_id ON long_term_memory(user_id)
            """))
            
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id VARCHAR(255) PRIMARY KEY,
                    preferences JSONB DEFAULT '{}',
                    interests JSONB DEFAULT '[]',
                    writing_style VARCHAR(255),
                    tone_preference VARCHAR(255),
                    niche VARCHAR(255),
                    constraints JSONB DEFAULT '[]',
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
        
        self._initialized = True
    
    async def _get_session(self):
        """获取数据库会话"""
        await self._ensure_initialized()
        return self._session_factory()
    
    async def store(self, entry: MemoryEntry) -> bool:
        """存储记忆条目"""
        from sqlalchemy import text
        
        try:
            async with await self._get_session() as session:
                await session.execute(
                    text("""
                        INSERT INTO long_term_memory 
                        (id, content, user_id, thread_id, memory_type, importance, metadata, created_at, updated_at)
                        VALUES (:id, :content, :user_id, :thread_id, :memory_type, :importance, :metadata, :created_at, :updated_at)
                        ON CONFLICT (id) DO UPDATE SET
                            content = EXCLUDED.content,
                            importance = EXCLUDED.importance,
                            metadata = EXCLUDED.metadata,
                            updated_at = EXCLUDED.updated_at,
                            access_count = long_term_memory.access_count + 1
                    """),
                    {
                        "id": entry.id,
                        "content": entry.content,
                        "user_id": entry.user_id,
                        "thread_id": entry.thread_id,
                        "memory_type": entry.memory_type.value,
                        "importance": entry.importance,
                        "metadata": json.dumps(entry.metadata),
                        "created_at": entry.created_at,
                        "updated_at": datetime.now()
                    }
                )
                await session.commit()
                return True
        except Exception as e:
            print(f"Error storing long-term memory: {e}")
            return False
    
    async def retrieve(self, entry_id: str) -> Optional[MemoryEntry]:
        """检索记忆条目"""
        from sqlalchemy import text
        
        try:
            async with await self._get_session() as session:
                result = await session.execute(
                    text("SELECT * FROM long_term_memory WHERE id = :id"),
                    {"id": entry_id}
                )
                row = result.fetchone()
                
                if row:
                    # 更新访问计数
                    await session.execute(
                        text("""
                            UPDATE long_term_memory 
                            SET access_count = access_count + 1 
                            WHERE id = :id
                        """),
                        {"id": entry_id}
                    )
                    await session.commit()
                    
                    return MemoryEntry(
                        id=row.id,
                        content=row.content,
                        memory_type=MemoryType(row.memory_type),
                        user_id=row.user_id,
                        thread_id=row.thread_id,
                        metadata=row.metadata if isinstance(row.metadata, dict) else json.loads(row.metadata or "{}"),
                        importance=row.importance,
                        access_count=row.access_count,
                        created_at=row.created_at,
                        updated_at=row.updated_at
                    )
                
                return None
        except Exception as e:
            print(f"Error retrieving long-term memory: {e}")
            return None
    
    async def search(self, query: MemoryQuery) -> MemorySearchResult:
        """搜索记忆条目"""
        from sqlalchemy import text
        import time
        
        start_time = time.time()
        
        try:
            async with await self._get_session() as session:
                # 构建查询
                sql = "SELECT * FROM long_term_memory WHERE 1=1"
                params = {}
                
                if query.user_id:
                    sql += " AND user_id = :user_id"
                    params["user_id"] = query.user_id
                
                if query.thread_id:
                    sql += " AND thread_id = :thread_id"
                    params["thread_id"] = query.thread_id
                
                if query.memory_type:
                    sql += " AND memory_type = :memory_type"
                    params["memory_type"] = query.memory_type.value
                
                if query.min_importance > 0:
                    sql += " AND importance >= :min_importance"
                    params["min_importance"] = query.min_importance
                
                if query.query_text:
                    sql += " AND content ILIKE :query_text"
                    params["query_text"] = f"%{query.query_text}%"
                
                sql += " ORDER BY importance DESC, updated_at DESC"
                sql += f" LIMIT {query.limit}"
                
                result = await session.execute(text(sql), params)
                rows = result.fetchall()
                
                entries = [
                    MemoryEntry(
                        id=row.id,
                        content=row.content,
                        memory_type=MemoryType(row.memory_type),
                        user_id=row.user_id,
                        thread_id=row.thread_id,
                        metadata=row.metadata if isinstance(row.metadata, dict) else json.loads(row.metadata or "{}"),
                        importance=row.importance,
                        access_count=row.access_count,
                        created_at=row.created_at,
                        updated_at=row.updated_at
                    )
                    for row in rows
                ]
                
                return MemorySearchResult(
                    entries=entries,
                    total_count=len(entries),
                    query_time=time.time() - start_time
                )
        except Exception as e:
            print(f"Error searching long-term memory: {e}")
            return MemorySearchResult(entries=[], total_count=0)
    
    async def update(self, entry_id: str, updates: Dict[str, Any]) -> bool:
        """更新记忆条目"""
        from sqlalchemy import text
        
        try:
            async with await self._get_session() as session:
                # 构建更新语句
                set_clauses = []
                params = {"id": entry_id}
                
                for key, value in updates.items():
                    if key in ["content", "importance", "user_id", "thread_id"]:
                        set_clauses.append(f"{key} = :{key}")
                        params[key] = value
                    elif key == "metadata":
                        set_clauses.append("metadata = :metadata")
                        params["metadata"] = json.dumps(value)
                
                if set_clauses:
                    set_clauses.append("updated_at = :updated_at")
                    params["updated_at"] = datetime.now()
                    
                    sql = f"UPDATE long_term_memory SET {', '.join(set_clauses)} WHERE id = :id"
                    await session.execute(text(sql), params)
                    await session.commit()
                    return True
                
                return False
        except Exception as e:
            print(f"Error updating long-term memory: {e}")
            return False
    
    async def delete(self, entry_id: str) -> bool:
        """删除记忆条目"""
        from sqlalchemy import text
        
        try:
            async with await self._get_session() as session:
                await session.execute(
                    text("DELETE FROM long_term_memory WHERE id = :id"),
                    {"id": entry_id}
                )
                await session.commit()
                return True
        except Exception as e:
            print(f"Error deleting long-term memory: {e}")
            return False
    
    async def clear(
        self,
        user_id: Optional[str] = None,
        thread_id: Optional[str] = None
    ) -> int:
        """清空记忆"""
        from sqlalchemy import text
        
        try:
            async with await self._get_session() as session:
                sql = "DELETE FROM long_term_memory WHERE 1=1"
                params = {}
                
                if user_id:
                    sql += " AND user_id = :user_id"
                    params["user_id"] = user_id
                
                if thread_id:
                    sql += " AND thread_id = :thread_id"
                    params["thread_id"] = thread_id
                
                result = await session.execute(text(sql), params)
                await session.commit()
                return result.rowcount
        except Exception as e:
            print(f"Error clearing long-term memory: {e}")
            return 0
    
    # ==================== 用户档案方法 ====================
    
    async def get_user_profile(self, user_id: str) -> Optional[UserProfile]:
        """获取用户档案"""
        from sqlalchemy import text
        
        try:
            async with await self._get_session() as session:
                result = await session.execute(
                    text("SELECT * FROM user_profiles WHERE user_id = :user_id"),
                    {"user_id": user_id}
                )
                row = result.fetchone()
                
                if row:
                    return UserProfile(
                        user_id=row.user_id,
                        preferences=row.preferences if isinstance(row.preferences, dict) else json.loads(row.preferences or "{}"),
                        interests=row.interests if isinstance(row.interests, list) else json.loads(row.interests or "[]"),
                        writing_style=row.writing_style,
                        tone_preference=row.tone_preference,
                        niche=row.niche,
                        constraints=row.constraints if isinstance(row.constraints, list) else json.loads(row.constraints or "[]"),
                        metadata=row.metadata if isinstance(row.metadata, dict) else json.loads(row.metadata or "{}"),
                        created_at=row.created_at,
                        updated_at=row.updated_at
                    )
                
                return None
        except Exception as e:
            print(f"Error getting user profile: {e}")
            return None
    
    async def save_user_profile(self, profile: UserProfile) -> bool:
        """保存用户档案"""
        from sqlalchemy import text
        
        try:
            async with await self._get_session() as session:
                await session.execute(
                    text("""
                        INSERT INTO user_profiles 
                        (user_id, preferences, interests, writing_style, tone_preference, niche, constraints, metadata, created_at, updated_at)
                        VALUES (:user_id, :preferences, :interests, :writing_style, :tone_preference, :niche, :constraints, :metadata, :created_at, :updated_at)
                        ON CONFLICT (user_id) DO UPDATE SET
                            preferences = EXCLUDED.preferences,
                            interests = EXCLUDED.interests,
                            writing_style = EXCLUDED.writing_style,
                            tone_preference = EXCLUDED.tone_preference,
                            niche = EXCLUDED.niche,
                            constraints = EXCLUDED.constraints,
                            metadata = EXCLUDED.metadata,
                            updated_at = EXCLUDED.updated_at
                    """),
                    {
                        "user_id": profile.user_id,
                        "preferences": json.dumps(profile.preferences),
                        "interests": json.dumps(profile.interests),
                        "writing_style": profile.writing_style,
                        "tone_preference": profile.tone_preference,
                        "niche": profile.niche,
                        "constraints": json.dumps(profile.constraints),
                        "metadata": json.dumps(profile.metadata),
                        "created_at": profile.created_at,
                        "updated_at": datetime.now()
                    }
                )
                await session.commit()
                return True
        except Exception as e:
            print(f"Error saving user profile: {e}")
            return False
    
    async def update_user_preferences(
        self,
        user_id: str,
        preferences: Dict[str, Any]
    ) -> bool:
        """更新用户偏好"""
        profile = await self.get_user_profile(user_id)
        
        if profile:
            profile.preferences.update(preferences)
            profile.updated_at = datetime.now()
            return await self.save_user_profile(profile)
        else:
            # 创建新档案
            profile = UserProfile(user_id=user_id, preferences=preferences)
            return await self.save_user_profile(profile)
