"""
LangGraph 状态定义
定义多 Agent 协作的共享状态
"""

from typing import Any, Dict, List, Optional, Annotated, TypedDict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import operator


class WorkflowStatus(str, Enum):
    """工作流状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentOutput(TypedDict, total=False):
    """Agent 输出结构"""
    agent_name: str
    success: bool
    output: Any
    error: Optional[str]
    execution_time: float
    timestamp: str


class GraphState(TypedDict, total=False):
    """
    LangGraph 共享状态
    所有 Agent 通过这个状态进行信息交换
    """
    
    # ==================== 基础信息 ====================
    thread_id: str  # 会话线程 ID
    user_id: Optional[str]  # 用户 ID
    session_id: str  # 会话 ID
    
    # ==================== 输入输出 ====================
    user_input: str  # 用户原始输入
    final_output: Optional[str]  # 最终输出
    
    # ==================== 工作流控制 ====================
    status: WorkflowStatus  # 当前状态
    current_agent: str  # 当前执行的 Agent
    next_agent: Optional[str]  # 下一个要执行的 Agent
    agent_sequence: List[str]  # Agent 执行序列
    iteration_count: int  # 迭代次数
    max_iterations: int  # 最大迭代次数
    
    # ==================== Agent 输出 ====================
    # 使用 Annotated 支持追加操作
    agent_outputs: Annotated[List[AgentOutput], operator.add]
    
    # ==================== Supervisor 决策 ====================
    supervisor_decision: Optional[Dict[str, Any]]
    
    # ==================== Searcher 结果 ====================
    search_results: Optional[Dict[str, Any]]
    
    # ==================== Writer 结果 ====================
    generated_content: Optional[Dict[str, Any]]
    
    # ==================== Reviewer 结果 ====================
    review_result: Optional[Dict[str, Any]]
    
    # ==================== 错误处理 ====================
    errors: Annotated[List[str], operator.add]
    retry_count: int
    
    # ==================== 元数据 ====================
    metadata: Dict[str, Any]
    created_at: str
    updated_at: str


def create_initial_state(
    thread_id: str,
    user_input: str,
    user_id: Optional[str] = None,
    max_iterations: int = 10
) -> GraphState:
    """
    创建初始状态
    
    Args:
        thread_id: 线程 ID
        user_input: 用户输入
        user_id: 用户 ID
        max_iterations: 最大迭代次数
        
    Returns:
        GraphState: 初始状态
    """
    import uuid
    
    return GraphState(
        thread_id=thread_id,
        user_id=user_id,
        session_id=str(uuid.uuid4()),
        user_input=user_input,
        final_output=None,
        status=WorkflowStatus.PENDING,
        current_agent="supervisor",
        next_agent=None,
        agent_sequence=[],
        iteration_count=0,
        max_iterations=max_iterations,
        agent_outputs=[],
        supervisor_decision=None,
        search_results=None,
        generated_content=None,
        review_result=None,
        errors=[],
        retry_count=0,
        metadata={},
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat()
    )


def update_state_timestamp(state: GraphState) -> GraphState:
    """更新状态时间戳"""
    state["updated_at"] = datetime.now().isoformat()
    return state


def add_agent_output(
    state: GraphState,
    agent_name: str,
    success: bool,
    output: Any,
    error: Optional[str] = None,
    execution_time: float = 0.0
) -> GraphState:
    """
    添加 Agent 输出到状态
    
    Args:
        state: 当前状态
        agent_name: Agent 名称
        success: 是否成功
        output: 输出内容
        error: 错误信息
        execution_time: 执行时间
        
    Returns:
        GraphState: 更新后的状态
    """
    agent_output = AgentOutput(
        agent_name=agent_name,
        success=success,
        output=output,
        error=error,
        execution_time=execution_time,
        timestamp=datetime.now().isoformat()
    )
    
    # 由于使用了 Annotated[..., operator.add]，直接返回列表即可
    return {"agent_outputs": [agent_output]}


def get_last_agent_output(state: GraphState) -> Optional[AgentOutput]:
    """获取最后一个 Agent 的输出"""
    outputs = state.get("agent_outputs", [])
    if outputs:
        return outputs[-1]
    return None


def get_agent_output_by_name(
    state: GraphState,
    agent_name: str
) -> Optional[AgentOutput]:
    """根据 Agent 名称获取输出"""
    outputs = state.get("agent_outputs", [])
    for output in reversed(outputs):
        if output.get("agent_name") == agent_name:
            return output
    return None


def is_workflow_complete(state: GraphState) -> bool:
    """检查工作流是否完成"""
    return state.get("status") in [
        WorkflowStatus.COMPLETED,
        WorkflowStatus.FAILED,
        WorkflowStatus.CANCELLED
    ]


def should_continue(state: GraphState) -> bool:
    """检查是否应该继续执行"""
    # 检查迭代次数
    if state.get("iteration_count", 0) >= state.get("max_iterations", 10):
        return False
    
    # 检查状态
    if is_workflow_complete(state):
        return False
    
    # 检查是否有下一个 Agent
    if state.get("next_agent") is None and state.get("current_agent") != "supervisor":
        return False
    
    return True


@dataclass
class StateSnapshot:
    """状态快照，用于调试和回溯"""
    state: GraphState
    timestamp: datetime = field(default_factory=datetime.now)
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "state": dict(self.state),
            "timestamp": self.timestamp.isoformat(),
            "description": self.description
        }


class StateHistory:
    """状态历史记录"""
    
    def __init__(self, max_snapshots: int = 50):
        self.snapshots: List[StateSnapshot] = []
        self.max_snapshots = max_snapshots
    
    def add_snapshot(
        self,
        state: GraphState,
        description: str = ""
    ) -> None:
        """添加快照"""
        snapshot = StateSnapshot(
            state=state.copy(),
            description=description
        )
        self.snapshots.append(snapshot)
        
        # 限制快照数量
        if len(self.snapshots) > self.max_snapshots:
            self.snapshots = self.snapshots[-self.max_snapshots:]
    
    def get_latest(self) -> Optional[StateSnapshot]:
        """获取最新快照"""
        if self.snapshots:
            return self.snapshots[-1]
        return None
    
    def get_by_agent(self, agent_name: str) -> List[StateSnapshot]:
        """获取特定 Agent 的快照"""
        return [
            s for s in self.snapshots
            if s.state.get("current_agent") == agent_name
        ]
    
    def clear(self) -> None:
        """清空历史"""
        self.snapshots.clear()
