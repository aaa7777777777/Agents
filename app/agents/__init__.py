"""
Agent 角色模块
包含所有具体的 Agent 实现
"""

from .supervisor_agent import SupervisorAgent
from .searcher_agent import SearcherAgent
from .writer_agent import WriterAgent
from .reviewer_agent import ReviewerAgent

__all__ = [
    "SupervisorAgent",
    "SearcherAgent",
    "WriterAgent",
    "ReviewerAgent",
]


def create_agent_team():
    """
    创建完整的 Agent 团队
    
    Returns:
        Dict[str, BaseAgent]: Agent 字典
    """
    return {
        "supervisor": SupervisorAgent(),
        "searcher": SearcherAgent(),
        "writer": WriterAgent(),
        "reviewer": ReviewerAgent(),
    }
