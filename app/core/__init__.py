"""
核心抽象层
包含所有基类和核心组件
"""

from .base_agent import (
    BaseAgent,
    AgentRole,
    AgentStatus,
    AgentMessage,
    AgentContext,
    AgentResult
)

from .base_skill import (
    BaseSkill,
    SkillCategory,
    SkillParameter,
    SkillDefinition,
    SkillResult,
    skill
)

from .base_memory import (
    BaseMemory,
    MemoryType,
    MemoryEntry,
    MemoryQuery,
    MemorySearchResult
)

from .template_engine import (
    TemplateEngine,
    PromptBuilder,
    template_engine
)

__all__ = [
    # Agent 相关
    "BaseAgent",
    "AgentRole",
    "AgentStatus",
    "AgentMessage",
    "AgentContext",
    "AgentResult",
    # Skill 相关
    "BaseSkill",
    "SkillCategory",
    "SkillParameter",
    "SkillDefinition",
    "SkillResult",
    "skill",
    # Memory 相关
    "BaseMemory",
    "MemoryType",
    "MemoryEntry",
    "MemoryQuery",
    "MemorySearchResult",
    # Template 相关
    "TemplateEngine",
    "PromptBuilder",
    "template_engine",
]
