"""
语义记忆（知识库）
基于向量数据库实现的 RAG 知识检索
"""

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
from app.services.vector_db import (
    BaseVectorDB,
    VectorDocument,
    VectorSearchResult as VectorResult,
    EmbeddingService,
    get_vector_db,
    get_embedding_service
)
from app.config import settings


class SemanticMemory(BaseMemory):
    """
    语义记忆实现
    用于存储和检索知识库内容，支持：
    - 语义相似度搜索
    - RAG 增强检索
    - 知识图谱关联
    """
    
    def __init__(
        self,
        vector_db: Optional[BaseVectorDB] = None,
        embedding_service: Optional[EmbeddingService] = None,
        collection_name: Optional[str] = None
    ):
        super().__init__(MemoryType.SEMANTIC)
        self.collection_name = collection_name or settings.QDRANT_COLLECTION
        self.vector_db = vector_db or get_vector_db(self.collection_name)
        self.embedding_service = embedding_service or get_embedding_service()
        self._initialized = False
    
    async def _ensure_initialized(self):
        """确保向量数据库已初始化"""
        if self._initialized:
            return
        
        await self.vector_db.create_collection(settings.EMBEDDING_DIM)
        self._initialized = True
    
    def _generate_embedding(self, text: str) -> List[float]:
        """生成文本嵌入向量"""
        return self.embedding_service.embed_single(text)
    
    async def store(self, entry: MemoryEntry) -> bool:
        """存储记忆条目"""
        await self._ensure_initialized()
        
        try:
            # 生成嵌入向量
            embedding = self._generate_embedding(entry.content)
            
            # 构建向量文档
            doc = VectorDocument(
                id=entry.id,
                content=entry.content,
                embedding=embedding,
                metadata={
                    "user_id": entry.user_id,
                    "thread_id": entry.thread_id,
                    "memory_type": entry.memory_type.value,
                    "importance": entry.importance,
                    "created_at": entry.created_at.isoformat(),
                    **entry.metadata
                }
            )
            
            return await self.vector_db.insert([doc])
        except Exception as e:
            print(f"Error storing semantic memory: {e}")
            return False
    
    async def retrieve(self, entry_id: str) -> Optional[MemoryEntry]:
        """检索记忆条目（通过 ID）"""
        # 向量数据库通常不支持直接 ID 查询，需要通过搜索实现
        # 这里使用元数据过滤
        query = MemoryQuery(
            memory_type=self.memory_type,
            limit=1,
            metadata_filters={"id": entry_id}
        )
        result = await self.search(query)
        
        if result.entries:
            return result.entries[0]
        return None
    
    async def search(self, query: MemoryQuery) -> MemorySearchResult:
        """语义搜索记忆条目"""
        await self._ensure_initialized()
        
        import time
        start_time = time.time()
        
        try:
            # 如果有查询文本，生成嵌入向量进行语义搜索
            if query.query_text:
                query_embedding = self._generate_embedding(query.query_text)
                
                # 构建过滤条件
                filters = {}
                if query.user_id:
                    filters["user_id"] = query.user_id
                if query.thread_id:
                    filters["thread_id"] = query.thread_id
                if query.metadata_filters:
                    filters.update(query.metadata_filters)
                
                # 执行向量搜索
                vector_result = await self.vector_db.search(
                    query_embedding=query_embedding,
                    limit=query.limit,
                    filters=filters if filters else None
                )
                
                # 转换结果
                entries = []
                for doc in vector_result.documents:
                    # 应用重要性过滤
                    importance = doc.metadata.get("importance", 0.5)
                    if importance < query.min_importance:
                        continue
                    
                    entries.append(MemoryEntry(
                        id=doc.id,
                        content=doc.content,
                        memory_type=self.memory_type,
                        user_id=doc.metadata.get("user_id"),
                        thread_id=doc.metadata.get("thread_id"),
                        metadata={
                            k: v for k, v in doc.metadata.items()
                            if k not in ["user_id", "thread_id", "memory_type", "importance", "created_at"]
                        },
                        importance=importance
                    ))
                
                return MemorySearchResult(
                    entries=entries,
                    total_count=len(entries),
                    query_time=time.time() - start_time
                )
            else:
                # 没有查询文本，返回空结果
                return MemorySearchResult(
                    entries=[],
                    total_count=0,
                    query_time=time.time() - start_time
                )
        except Exception as e:
            print(f"Error searching semantic memory: {e}")
            return MemorySearchResult(entries=[], total_count=0)
    
    async def update(self, entry_id: str, updates: Dict[str, Any]) -> bool:
        """更新记忆条目"""
        try:
            # 获取现有条目
            entry = await self.retrieve(entry_id)
            if not entry:
                return False
            
            # 更新内容
            if "content" in updates:
                entry.content = updates["content"]
            if "importance" in updates:
                entry.importance = updates["importance"]
            if "metadata" in updates:
                entry.metadata.update(updates["metadata"])
            
            # 重新存储（会覆盖）
            return await self.store(entry)
        except Exception as e:
            print(f"Error updating semantic memory: {e}")
            return False
    
    async def delete(self, entry_id: str) -> bool:
        """删除记忆条目"""
        try:
            return await self.vector_db.delete([entry_id])
        except Exception as e:
            print(f"Error deleting semantic memory: {e}")
            return False
    
    async def clear(
        self,
        user_id: Optional[str] = None,
        thread_id: Optional[str] = None
    ) -> int:
        """清空记忆"""
        # 向量数据库通常不支持条件删除，需要重建集合
        # 这里简化处理
        try:
            if user_id is None and thread_id is None:
                await self.vector_db.delete_collection()
                self._initialized = False
                return -1  # 表示全部清空
            
            # 对于条件删除，需要先搜索再删除
            # 这里返回 0 表示不支持
            return 0
        except Exception as e:
            print(f"Error clearing semantic memory: {e}")
            return 0
    
    # ==================== RAG 相关方法 ====================
    
    async def add_knowledge(
        self,
        content: str,
        source: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        importance: float = 0.5
    ) -> bool:
        """添加知识条目"""
        entry = MemoryEntry(
            id=str(uuid.uuid4()),
            content=content,
            memory_type=self.memory_type,
            metadata={
                "source": source,
                "category": category,
                "tags": tags or [],
                "type": "knowledge"
            },
            importance=importance
        )
        return await self.store(entry)
    
    async def search_knowledge(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 5,
        min_score: float = 0.5
    ) -> List[Dict[str, Any]]:
        """搜索知识库"""
        await self._ensure_initialized()
        
        try:
            query_embedding = self._generate_embedding(query)
            
            filters = {"type": "knowledge"}
            if category:
                filters["category"] = category
            
            vector_result = await self.vector_db.search(
                query_embedding=query_embedding,
                limit=limit,
                filters=filters
            )
            
            results = []
            for doc in vector_result.documents:
                if doc.score >= min_score:
                    results.append({
                        "content": doc.content,
                        "score": doc.score,
                        "source": doc.metadata.get("source"),
                        "category": doc.metadata.get("category"),
                        "tags": doc.metadata.get("tags", [])
                    })
            
            return results
        except Exception as e:
            print(f"Error searching knowledge: {e}")
            return []
    
    async def get_context_for_query(
        self,
        query: str,
        max_tokens: int = 1000,
        limit: int = 3
    ) -> str:
        """
        获取查询相关的上下文
        用于 RAG 增强生成
        """
        results = await self.search_knowledge(query, limit=limit)
        
        if not results:
            return ""
        
        context_parts = []
        total_length = 0
        
        for result in results:
            content = result["content"]
            if total_length + len(content) > max_tokens:
                # 截断以适应 token 限制
                remaining = max_tokens - total_length
                if remaining > 100:
                    content = content[:remaining] + "..."
                else:
                    break
            
            context_parts.append(f"[来源: {result.get('source', '未知')}]\n{content}")
            total_length += len(content)
        
        return "\n\n---\n\n".join(context_parts)
    
    async def batch_add_knowledge(
        self,
        items: List[Dict[str, Any]]
    ) -> int:
        """批量添加知识条目"""
        success_count = 0
        
        for item in items:
            success = await self.add_knowledge(
                content=item.get("content", ""),
                source=item.get("source"),
                category=item.get("category"),
                tags=item.get("tags"),
                importance=item.get("importance", 0.5)
            )
            if success:
                success_count += 1
        
        return success_count
