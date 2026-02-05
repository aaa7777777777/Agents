"""
LangGraph 边定义
定义 Agent 之间的路由逻辑
"""

from typing import Literal, Union
from app.orchestration.graph_state import (
    GraphState,
    WorkflowStatus,
    get_last_agent_output,
    is_workflow_complete
)


# 定义可能的路由目标
RouteTarget = Literal[
    "supervisor",
    "searcher", 
    "writer",
    "reviewer",
    "end",
    "error"
]


def route_from_supervisor(state: GraphState) -> RouteTarget:
    """
    从 Supervisor 路由到下一个 Agent
    
    根据 Supervisor 的决策确定下一步
    """
    # 检查是否有错误
    if state.get("errors"):
        return "error"
    
    # 获取 Supervisor 决策
    decision = state.get("supervisor_decision", {})
    agents = decision.get("agents", [])
    
    if not agents:
        # 没有指定 Agent，默认使用 writer
        return "writer"
    
    # 返回第一个要执行的 Agent
    first_agent = agents[0]
    
    if first_agent == "searcher":
        return "searcher"
    elif first_agent == "writer":
        return "writer"
    elif first_agent == "reviewer":
        return "reviewer"
    else:
        return "writer"


def route_from_searcher(state: GraphState) -> RouteTarget:
    """
    从 Searcher 路由到下一个 Agent
    
    搜索完成后通常进入写作阶段
    """
    # 检查搜索是否成功
    last_output = get_last_agent_output(state)
    
    if last_output and not last_output.get("success", False):
        # 搜索失败，检查重试次数
        if state.get("retry_count", 0) < 2:
            return "searcher"  # 重试
        else:
            return "writer"  # 跳过搜索，直接写作
    
    # 检查决策中的 Agent 序列
    decision = state.get("supervisor_decision", {})
    agents = decision.get("agents", [])
    
    try:
        current_idx = agents.index("searcher")
        if current_idx < len(agents) - 1:
            next_agent = agents[current_idx + 1]
            if next_agent in ["writer", "reviewer"]:
                return next_agent
    except ValueError:
        pass
    
    # 默认进入写作
    return "writer"


def route_from_writer(state: GraphState) -> RouteTarget:
    """
    从 Writer 路由到下一个 Agent
    
    写作完成后通常进入审核阶段
    """
    # 检查写作是否成功
    last_output = get_last_agent_output(state)
    
    if last_output and not last_output.get("success", False):
        # 写作失败
        if state.get("retry_count", 0) < 2:
            return "writer"  # 重试
        else:
            return "error"  # 多次失败，报错
    
    # 检查是否有生成的内容
    if not state.get("generated_content"):
        return "writer"  # 没有内容，重新生成
    
    # 检查决策中的 Agent 序列
    decision = state.get("supervisor_decision", {})
    agents = decision.get("agents", [])
    
    # 如果决策中包含 reviewer，进入审核
    if "reviewer" in agents:
        return "reviewer"
    
    # 否则直接结束
    return "end"


def route_from_reviewer(state: GraphState) -> RouteTarget:
    """
    从 Reviewer 路由
    
    根据审核结果决定是通过、修改还是重写
    """
    review_result = state.get("review_result", {})
    
    if not review_result:
        # 没有审核结果，重新审核
        return "reviewer"
    
    passed = review_result.get("passed", False)
    action = review_result.get("action", "approve")
    
    if passed or action == "approve":
        # 审核通过，结束
        return "end"
    elif action == "revise":
        # 需要修改，回到 writer
        # 检查迭代次数，避免无限循环
        if state.get("iteration_count", 0) < state.get("max_iterations", 10) - 1:
            return "writer"
        else:
            return "end"  # 达到最大迭代，强制结束
    elif action == "rewrite":
        # 需要重写
        if state.get("iteration_count", 0) < state.get("max_iterations", 10) - 2:
            return "searcher"  # 重新搜索素材
        else:
            return "end"
    else:
        return "end"


def should_end(state: GraphState) -> bool:
    """
    判断是否应该结束工作流
    """
    # 检查状态
    if is_workflow_complete(state):
        return True
    
    # 检查迭代次数
    if state.get("iteration_count", 0) >= state.get("max_iterations", 10):
        return True
    
    # 检查是否有最终输出
    if state.get("final_output") and state.get("status") == WorkflowStatus.COMPLETED:
        return True
    
    return False


def get_conditional_edges():
    """
    获取条件边配置
    
    返回用于 LangGraph 的条件边定义
    """
    return {
        "supervisor": {
            "function": route_from_supervisor,
            "mapping": {
                "searcher": "searcher",
                "writer": "writer",
                "reviewer": "reviewer",
                "end": "end",
                "error": "error"
            }
        },
        "searcher": {
            "function": route_from_searcher,
            "mapping": {
                "searcher": "searcher",
                "writer": "writer",
                "reviewer": "reviewer",
                "end": "end"
            }
        },
        "writer": {
            "function": route_from_writer,
            "mapping": {
                "writer": "writer",
                "reviewer": "reviewer",
                "end": "end",
                "error": "error"
            }
        },
        "reviewer": {
            "function": route_from_reviewer,
            "mapping": {
                "searcher": "searcher",
                "writer": "writer",
                "end": "end"
            }
        }
    }


class EdgeRouter:
    """
    边路由器
    提供更灵活的路由控制
    """
    
    def __init__(self):
        self._custom_routes = {}
    
    def add_custom_route(
        self,
        from_agent: str,
        condition: callable,
        to_agent: str
    ) -> None:
        """
        添加自定义路由规则
        
        Args:
            from_agent: 源 Agent
            condition: 条件函数，接收 state 返回 bool
            to_agent: 目标 Agent
        """
        if from_agent not in self._custom_routes:
            self._custom_routes[from_agent] = []
        
        self._custom_routes[from_agent].append({
            "condition": condition,
            "target": to_agent
        })
    
    def route(self, from_agent: str, state: GraphState) -> RouteTarget:
        """
        执行路由
        
        Args:
            from_agent: 源 Agent
            state: 当前状态
            
        Returns:
            RouteTarget: 目标 Agent
        """
        # 先检查自定义路由
        if from_agent in self._custom_routes:
            for rule in self._custom_routes[from_agent]:
                if rule["condition"](state):
                    return rule["target"]
        
        # 使用默认路由
        if from_agent == "supervisor":
            return route_from_supervisor(state)
        elif from_agent == "searcher":
            return route_from_searcher(state)
        elif from_agent == "writer":
            return route_from_writer(state)
        elif from_agent == "reviewer":
            return route_from_reviewer(state)
        else:
            return "end"
