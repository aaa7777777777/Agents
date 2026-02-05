"""
Agent 抽象基类
定义所有 Agent 的通用接口和基础行为
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import uuid
from datetime import datetime


class AgentRole(str, Enum):
    """Agent 角色枚举"""
    SUPERVISOR = "supervisor"
    SEARCHER = "searcher"
    WRITER = "writer"
    REVIEWER = "reviewer"
    PLANNER = "planner"


class AgentStatus(str, Enum):
    """Agent 状态枚举"""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING = "waiting"


@dataclass
class AgentMessage:
    """Agent 消息结构"""
    role: str  # user, assistant, system, tool
    content: str
    name: Optional[str] = None
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentContext:
    """Agent 执行上下文"""
    thread_id: str
    user_id: Optional[str] = None
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    messages: List[AgentMessage] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_message(self, role: str, content: str, **kwargs) -> None:
        """添加消息到上下文"""
        self.messages.append(AgentMessage(role=role, content=content, **kwargs))
    
    def get_messages_for_llm(self) -> List[Dict[str, str]]:
        """获取用于 LLM 调用的消息格式"""
        return [
            {"role": msg.role, "content": msg.content}
            for msg in self.messages
        ]
    
    def set_variable(self, key: str, value: Any) -> None:
        """设置上下文变量"""
        self.variables[key] = value
    
    def get_variable(self, key: str, default: Any = None) -> Any:
        """获取上下文变量"""
        return self.variables.get(key, default)


@dataclass
class AgentResult:
    """Agent 执行结果"""
    success: bool
    output: Any
    agent_name: str
    status: AgentStatus = AgentStatus.COMPLETED
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    execution_time: float = 0.0
    token_usage: Dict[str, int] = field(default_factory=dict)
    
    @classmethod
    def success_result(cls, output: Any, agent_name: str, **kwargs) -> "AgentResult":
        """创建成功结果"""
        return cls(success=True, output=output, agent_name=agent_name, **kwargs)
    
    @classmethod
    def failure_result(cls, error: str, agent_name: str, **kwargs) -> "AgentResult":
        """创建失败结果"""
        return cls(
            success=False, 
            output=None, 
            agent_name=agent_name,
            status=AgentStatus.FAILED,
            error=error, 
            **kwargs
        )


class BaseAgent(ABC):
    """
    Agent 抽象基类
    所有具体 Agent 都必须继承此类并实现抽象方法
    """
    
    def __init__(
        self,
        name: str,
        role: AgentRole,
        description: str = "",
        llm_engine: Any = None,
        memory_manager: Any = None,
        skill_registry: Any = None,
    ):
        self.name = name
        self.role = role
        self.description = description
        self.llm_engine = llm_engine
        self.memory_manager = memory_manager
        self.skill_registry = skill_registry
        self.status = AgentStatus.IDLE
        self._system_prompt: Optional[str] = None
    
    @property
    def system_prompt(self) -> str:
        """获取系统提示词"""
        if self._system_prompt is None:
            self._system_prompt = self._build_system_prompt()
        return self._system_prompt
    
    @system_prompt.setter
    def system_prompt(self, value: str) -> None:
        """设置系统提示词"""
        self._system_prompt = value
    
    @abstractmethod
    def _build_system_prompt(self) -> str:
        """
        构建系统提示词
        子类必须实现此方法来定义 Agent 的人设和行为规范
        """
        pass
    
    @abstractmethod
    async def execute(self, context: AgentContext) -> AgentResult:
        """
        执行 Agent 的主要逻辑
        子类必须实现此方法
        
        Args:
            context: Agent 执行上下文
            
        Returns:
            AgentResult: 执行结果
        """
        pass
    
    async def pre_execute(self, context: AgentContext) -> None:
        """
        执行前的钩子方法
        可以在子类中重写以添加预处理逻辑
        """
        self.status = AgentStatus.RUNNING
    
    async def post_execute(self, context: AgentContext, result: AgentResult) -> None:
        """
        执行后的钩子方法
        可以在子类中重写以添加后处理逻辑
        """
        self.status = result.status
    
    async def run(self, context: AgentContext) -> AgentResult:
        """
        运行 Agent 的完整流程
        包含前置处理、执行和后置处理
        """
        import time
        start_time = time.time()
        
        try:
            await self.pre_execute(context)
            result = await self.execute(context)
            result.execution_time = time.time() - start_time
            await self.post_execute(context, result)
            return result
        except Exception as e:
            self.status = AgentStatus.FAILED
            return AgentResult.failure_result(
                error=str(e),
                agent_name=self.name,
                execution_time=time.time() - start_time
            )
    
    def get_available_skills(self) -> List[str]:
        """获取当前 Agent 可用的技能列表"""
        if self.skill_registry is None:
            return []
        return self.skill_registry.get_skills_for_agent(self.role)
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name={self.name}, role={self.role.value})>"
