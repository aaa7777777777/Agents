"""
服务适配层
包含所有外部服务的连接器
"""

from .llm_engine import (
    BaseLLMEngine,
    OllamaEngine,
    VLLMEngine,
    LLMEngineFactory,
    LLMMessage,
    LLMResponse,
    LLMConfig,
    LLMProvider,
    get_llm_engine
)

from .vector_db import (
    BaseVectorDB,
    QdrantClient,
    ChromaDBClient,
    VectorDBFactory,
    VectorDocument,
    VectorSearchResult,
    EmbeddingService,
    get_vector_db,
    get_embedding_service
)

from .cache import (
    RedisCache,
    SessionManager,
    ConversationHistory,
    get_cache,
    get_session_manager,
    get_conversation_history
)

__all__ = [
    # LLM 相关
    "BaseLLMEngine",
    "OllamaEngine",
    "VLLMEngine",
    "LLMEngineFactory",
    "LLMMessage",
    "LLMResponse",
    "LLMConfig",
    "LLMProvider",
    "get_llm_engine",
    # 向量数据库相关
    "BaseVectorDB",
    "QdrantClient",
    "ChromaDBClient",
    "VectorDBFactory",
    "VectorDocument",
    "VectorSearchResult",
    "EmbeddingService",
    "get_vector_db",
    "get_embedding_service",
    # 缓存相关
    "RedisCache",
    "SessionManager",
    "ConversationHistory",
    "get_cache",
    "get_session_manager",
    "get_conversation_history",
]
