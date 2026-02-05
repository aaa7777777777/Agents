"""
向量数据库客户端
支持 Qdrant 和 ChromaDB
"""

import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from app.config import settings


@dataclass
class VectorDocument:
    """向量文档"""
    id: str
    content: str
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    score: float = 0.0


@dataclass
class VectorSearchResult:
    """向量搜索结果"""
    documents: List[VectorDocument]
    total: int
    query_time: float = 0.0


class BaseVectorDB(ABC):
    """向量数据库抽象基类"""
    
    def __init__(self, collection_name: str):
        self.collection_name = collection_name
    
    @abstractmethod
    async def create_collection(self, dimension: int) -> bool:
        """创建集合"""
        pass
    
    @abstractmethod
    async def delete_collection(self) -> bool:
        """删除集合"""
        pass
    
    @abstractmethod
    async def insert(self, documents: List[VectorDocument]) -> bool:
        """插入文档"""
        pass
    
    @abstractmethod
    async def search(
        self,
        query_embedding: List[float],
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> VectorSearchResult:
        """向量搜索"""
        pass
    
    @abstractmethod
    async def delete(self, ids: List[str]) -> bool:
        """删除文档"""
        pass
    
    @abstractmethod
    async def update(self, document: VectorDocument) -> bool:
        """更新文档"""
        pass


class QdrantClient(BaseVectorDB):
    """Qdrant 向量数据库客户端"""
    
    def __init__(
        self,
        collection_name: str,
        host: Optional[str] = None,
        port: Optional[int] = None
    ):
        super().__init__(collection_name)
        self.host = host or settings.QDRANT_HOST
        self.port = port or settings.QDRANT_PORT
        self._client = None
    
    @property
    def client(self):
        """延迟初始化 Qdrant 客户端"""
        if self._client is None:
            from qdrant_client import QdrantClient as QC
            self._client = QC(host=self.host, port=self.port)
        return self._client
    
    async def create_collection(self, dimension: int) -> bool:
        """创建 Qdrant 集合"""
        from qdrant_client.models import Distance, VectorParams
        
        try:
            # 检查集合是否存在
            collections = self.client.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)
            
            if not exists:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=dimension,
                        distance=Distance.COSINE
                    )
                )
            return True
        except Exception as e:
            print(f"Error creating collection: {e}")
            return False
    
    async def delete_collection(self) -> bool:
        """删除 Qdrant 集合"""
        try:
            self.client.delete_collection(self.collection_name)
            return True
        except Exception as e:
            print(f"Error deleting collection: {e}")
            return False
    
    async def insert(self, documents: List[VectorDocument]) -> bool:
        """插入文档到 Qdrant"""
        from qdrant_client.models import PointStruct
        
        try:
            points = [
                PointStruct(
                    id=doc.id,
                    vector=doc.embedding,
                    payload={
                        "content": doc.content,
                        **doc.metadata
                    }
                )
                for doc in documents
                if doc.embedding is not None
            ]
            
            if points:
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=points
                )
            return True
        except Exception as e:
            print(f"Error inserting documents: {e}")
            return False
    
    async def search(
        self,
        query_embedding: List[float],
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> VectorSearchResult:
        """在 Qdrant 中搜索"""
        import time
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        
        start_time = time.time()
        
        try:
            # 构建过滤条件
            qdrant_filter = None
            if filters:
                conditions = [
                    FieldCondition(key=k, match=MatchValue(value=v))
                    for k, v in filters.items()
                ]
                qdrant_filter = Filter(must=conditions)
            
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=limit,
                query_filter=qdrant_filter
            )
            
            documents = [
                VectorDocument(
                    id=str(r.id),
                    content=r.payload.get("content", ""),
                    metadata={k: v for k, v in r.payload.items() if k != "content"},
                    score=r.score
                )
                for r in results
            ]
            
            return VectorSearchResult(
                documents=documents,
                total=len(documents),
                query_time=time.time() - start_time
            )
        except Exception as e:
            print(f"Error searching: {e}")
            return VectorSearchResult(documents=[], total=0)
    
    async def delete(self, ids: List[str]) -> bool:
        """从 Qdrant 删除文档"""
        from qdrant_client.models import PointIdsList
        
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=PointIdsList(points=ids)
            )
            return True
        except Exception as e:
            print(f"Error deleting documents: {e}")
            return False
    
    async def update(self, document: VectorDocument) -> bool:
        """更新 Qdrant 中的文档"""
        return await self.insert([document])


class ChromaDBClient(BaseVectorDB):
    """ChromaDB 向量数据库客户端"""
    
    def __init__(self, collection_name: str, persist_directory: Optional[str] = None):
        super().__init__(collection_name)
        self.persist_directory = persist_directory or "./chroma_data"
        self._client = None
        self._collection = None
    
    @property
    def client(self):
        """延迟初始化 ChromaDB 客户端"""
        if self._client is None:
            import chromadb
            from chromadb.config import Settings as ChromaSettings
            
            self._client = chromadb.Client(ChromaSettings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=self.persist_directory,
                anonymized_telemetry=False
            ))
        return self._client
    
    @property
    def collection(self):
        """获取或创建集合"""
        if self._collection is None:
            self._collection = self.client.get_or_create_collection(
                name=self.collection_name
            )
        return self._collection
    
    async def create_collection(self, dimension: int) -> bool:
        """创建 ChromaDB 集合"""
        try:
            self._collection = self.client.get_or_create_collection(
                name=self.collection_name
            )
            return True
        except Exception as e:
            print(f"Error creating collection: {e}")
            return False
    
    async def delete_collection(self) -> bool:
        """删除 ChromaDB 集合"""
        try:
            self.client.delete_collection(self.collection_name)
            self._collection = None
            return True
        except Exception as e:
            print(f"Error deleting collection: {e}")
            return False
    
    async def insert(self, documents: List[VectorDocument]) -> bool:
        """插入文档到 ChromaDB"""
        try:
            ids = [doc.id for doc in documents]
            embeddings = [doc.embedding for doc in documents if doc.embedding]
            contents = [doc.content for doc in documents]
            metadatas = [doc.metadata for doc in documents]
            
            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=contents,
                metadatas=metadatas
            )
            return True
        except Exception as e:
            print(f"Error inserting documents: {e}")
            return False
    
    async def search(
        self,
        query_embedding: List[float],
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> VectorSearchResult:
        """在 ChromaDB 中搜索"""
        import time
        
        start_time = time.time()
        
        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=limit,
                where=filters
            )
            
            documents = []
            if results["ids"] and results["ids"][0]:
                for i, doc_id in enumerate(results["ids"][0]):
                    documents.append(VectorDocument(
                        id=doc_id,
                        content=results["documents"][0][i] if results["documents"] else "",
                        metadata=results["metadatas"][0][i] if results["metadatas"] else {},
                        score=1 - results["distances"][0][i] if results["distances"] else 0
                    ))
            
            return VectorSearchResult(
                documents=documents,
                total=len(documents),
                query_time=time.time() - start_time
            )
        except Exception as e:
            print(f"Error searching: {e}")
            return VectorSearchResult(documents=[], total=0)
    
    async def delete(self, ids: List[str]) -> bool:
        """从 ChromaDB 删除文档"""
        try:
            self.collection.delete(ids=ids)
            return True
        except Exception as e:
            print(f"Error deleting documents: {e}")
            return False
    
    async def update(self, document: VectorDocument) -> bool:
        """更新 ChromaDB 中的文档"""
        try:
            self.collection.update(
                ids=[document.id],
                embeddings=[document.embedding] if document.embedding else None,
                documents=[document.content],
                metadatas=[document.metadata]
            )
            return True
        except Exception as e:
            print(f"Error updating document: {e}")
            return False


class EmbeddingService:
    """嵌入向量服务"""
    
    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.EMBEDDING_MODEL
        self._model = None
    
    @property
    def model(self):
        """延迟加载嵌入模型"""
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        return self._model
    
    def embed(self, texts: List[str]) -> List[List[float]]:
        """生成嵌入向量"""
        embeddings = self.model.encode(texts)
        return embeddings.tolist()
    
    def embed_single(self, text: str) -> List[float]:
        """生成单个文本的嵌入向量"""
        return self.embed([text])[0]


class VectorDBFactory:
    """向量数据库工厂"""
    
    _instances: Dict[str, BaseVectorDB] = {}
    
    @classmethod
    def get_client(
        cls,
        collection_name: Optional[str] = None,
        provider: Optional[str] = None
    ) -> BaseVectorDB:
        """获取向量数据库客户端"""
        collection_name = collection_name or settings.QDRANT_COLLECTION
        provider = provider or settings.VECTOR_DB_PROVIDER
        
        cache_key = f"{provider}_{collection_name}"
        
        if cache_key not in cls._instances:
            if provider == "qdrant":
                cls._instances[cache_key] = QdrantClient(collection_name)
            elif provider == "chroma":
                cls._instances[cache_key] = ChromaDBClient(collection_name)
            else:
                raise ValueError(f"Unsupported vector DB provider: {provider}")
        
        return cls._instances[cache_key]


# 便捷函数
def get_vector_db(collection_name: Optional[str] = None) -> BaseVectorDB:
    """获取默认向量数据库客户端"""
    return VectorDBFactory.get_client(collection_name)


def get_embedding_service() -> EmbeddingService:
    """获取嵌入服务"""
    return EmbeddingService()
