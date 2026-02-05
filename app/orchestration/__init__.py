"""
编排层模块
基于 LangGraph 的多 Agent 协作编排
"""

from .graph_state import (
    GraphState,
    WorkflowStatus,
    AgentOutput,
    create_initial_state,
    update_state_timestamp,
    add_agent_output,
    get_last_agent_output,
    get_agent_output_by_name,
    is_workflow_complete,
    should_continue,
    StateSnapshot,
    StateHistory
)

from .graph_edges import (
    RouteTarget,
    route_from_supervisor,
    route_from_searcher,
    route_from_writer,
    route_from_reviewer,
    should_end,
    get_conditional_edges,
    EdgeRouter
)

from .workflow import (
    AgentWorkflow,
    WorkflowBuilder,
    create_default_workflow
)

__all__ = [
    # 状态
    "GraphState",
    "WorkflowStatus",
    "AgentOutput",
    "create_initial_state",
    "update_state_timestamp",
    "add_agent_output",
    "get_last_agent_output",
    "get_agent_output_by_name",
    "is_workflow_complete",
    "should_continue",
    "StateSnapshot",
    "StateHistory",
    # 边
    "RouteTarget",
    "route_from_supervisor",
    "route_from_searcher",
    "route_from_writer",
    "route_from_reviewer",
    "should_end",
    "get_conditional_edges",
    "EdgeRouter",
    # 工作流
    "AgentWorkflow",
    "WorkflowBuilder",
    "create_default_workflow",
]
