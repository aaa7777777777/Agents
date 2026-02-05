"""
LangGraph 工作流定义
定义多 Agent 协作的 DAG 图
"""

import asyncio
import time
from typing import Any, Dict, Optional, Callable
from datetime import datetime

from app.orchestration.graph_state import (
    GraphState,
    WorkflowStatus,
    create_initial_state,
    update_state_timestamp,
    add_agent_output,
    is_workflow_complete,
    should_continue,
    StateHistory
)
from app.orchestration.graph_edges import (
    route_from_supervisor,
    route_from_searcher,
    route_from_writer,
    route_from_reviewer,
    EdgeRouter
)
from app.agents import (
    SupervisorAgent,
    SearcherAgent,
    WriterAgent,
    ReviewerAgent
)
from app.core.base_agent import AgentContext, AgentResult


class AgentWorkflow:
    """
    Agent 工作流
    协调多个 Agent 的执行
    """
    
    def __init__(
        self,
        max_iterations: int = 10,
        enable_history: bool = True
    ):
        """
        初始化工作流
        
        Args:
            max_iterations: 最大迭代次数
            enable_history: 是否启用历史记录
        """
        self.max_iterations = max_iterations
        self.enable_history = enable_history
        
        # 初始化 Agent
        self.agents = {
            "supervisor": SupervisorAgent(),
            "searcher": SearcherAgent(),
            "writer": WriterAgent(),
            "reviewer": ReviewerAgent()
        }
        
        # 路由器
        self.router = EdgeRouter()
        
        # 状态历史
        self.history = StateHistory() if enable_history else None
        
        # 回调函数
        self._on_agent_start: Optional[Callable] = None
        self._on_agent_end: Optional[Callable] = None
        self._on_workflow_end: Optional[Callable] = None
    
    def set_callbacks(
        self,
        on_agent_start: Optional[Callable] = None,
        on_agent_end: Optional[Callable] = None,
        on_workflow_end: Optional[Callable] = None
    ) -> None:
        """设置回调函数"""
        self._on_agent_start = on_agent_start
        self._on_agent_end = on_agent_end
        self._on_workflow_end = on_workflow_end
    
    async def run(
        self,
        user_input: str,
        thread_id: str,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        运行工作流
        
        Args:
            user_input: 用户输入
            thread_id: 线程 ID
            user_id: 用户 ID
            metadata: 元数据
            
        Returns:
            Dict: 执行结果
        """
        # 创建初始状态
        state = create_initial_state(
            thread_id=thread_id,
            user_input=user_input,
            user_id=user_id,
            max_iterations=self.max_iterations
        )
        
        if metadata:
            state["metadata"] = metadata
        
        state["status"] = WorkflowStatus.RUNNING
        
        # 记录初始状态
        if self.history:
            self.history.add_snapshot(state, "Workflow started")
        
        try:
            # 执行工作流
            while should_continue(state):
                state = await self._execute_step(state)
                state["iteration_count"] = state.get("iteration_count", 0) + 1
                
                # 记录状态
                if self.history:
                    self.history.add_snapshot(
                        state,
                        f"After {state['current_agent']}"
                    )
            
            # 设置最终输出
            state = self._finalize_output(state)
            state["status"] = WorkflowStatus.COMPLETED
            
        except Exception as e:
            state["status"] = WorkflowStatus.FAILED
            state["errors"] = state.get("errors", []) + [str(e)]
        
        # 回调
        if self._on_workflow_end:
            await self._safe_callback(self._on_workflow_end, state)
        
        return self._build_result(state)
    
    async def _execute_step(self, state: GraphState) -> GraphState:
        """执行单个步骤"""
        current_agent = state.get("current_agent", "supervisor")
        
        # 获取 Agent
        agent = self.agents.get(current_agent)
        if not agent:
            state["errors"] = state.get("errors", []) + [f"Unknown agent: {current_agent}"]
            state["next_agent"] = "end"
            return state
        
        # 回调
        if self._on_agent_start:
            await self._safe_callback(self._on_agent_start, current_agent, state)
        
        # 创建上下文
        context = self._create_context(state)
        
        # 执行 Agent
        start_time = time.time()
        result = await agent.execute(context)
        execution_time = time.time() - start_time
        
        # 更新状态
        state = self._update_state_from_result(
            state,
            current_agent,
            result,
            context,
            execution_time
        )
        
        # 回调
        if self._on_agent_end:
            await self._safe_callback(self._on_agent_end, current_agent, result, state)
        
        # 路由到下一个 Agent
        next_agent = self._route_next(current_agent, state)
        state["next_agent"] = next_agent
        
        if next_agent != "end" and next_agent != "error":
            state["current_agent"] = next_agent
            state["agent_sequence"] = state.get("agent_sequence", []) + [next_agent]
        
        return update_state_timestamp(state)
    
    def _create_context(self, state: GraphState) -> AgentContext:
        """从状态创建 Agent 上下文"""
        context = AgentContext(
            thread_id=state.get("thread_id", ""),
            user_id=state.get("user_id")
        )
        
        # 复制状态变量到上下文
        context.set_variable("user_input", state.get("user_input", ""))
        context.set_variable("supervisor_decision", state.get("supervisor_decision"))
        context.set_variable("search_results", state.get("search_results"))
        context.set_variable("generated_content", state.get("generated_content"))
        context.set_variable("review_result", state.get("review_result"))
        
        # 设置 Agent 参数
        decision = state.get("supervisor_decision", {})
        context.set_variable("agent_parameters", decision.get("parameters", {}))
        
        return context
    
    def _update_state_from_result(
        self,
        state: GraphState,
        agent_name: str,
        result: AgentResult,
        context: AgentContext,
        execution_time: float
    ) -> GraphState:
        """从 Agent 结果更新状态"""
        
        # 添加 Agent 输出
        output_update = add_agent_output(
            state,
            agent_name=agent_name,
            success=result.success,
            output=result.output,
            error=result.error,
            execution_time=execution_time
        )
        state["agent_outputs"] = state.get("agent_outputs", []) + output_update["agent_outputs"]
        
        # 根据 Agent 类型更新特定字段
        if agent_name == "supervisor" and result.success:
            state["supervisor_decision"] = result.output
        elif agent_name == "searcher" and result.success:
            state["search_results"] = result.output
        elif agent_name == "writer" and result.success:
            state["generated_content"] = result.output
        elif agent_name == "reviewer" and result.success:
            state["review_result"] = result.output
        
        # 从上下文同步变量
        if context.get_variable("supervisor_decision"):
            state["supervisor_decision"] = context.get_variable("supervisor_decision")
        if context.get_variable("search_results"):
            state["search_results"] = context.get_variable("search_results")
        if context.get_variable("generated_content"):
            state["generated_content"] = context.get_variable("generated_content")
        if context.get_variable("review_result"):
            state["review_result"] = context.get_variable("review_result")
        
        # 处理错误
        if not result.success:
            state["errors"] = state.get("errors", []) + [result.error or "Unknown error"]
            state["retry_count"] = state.get("retry_count", 0) + 1
        
        return state
    
    def _route_next(self, current_agent: str, state: GraphState) -> str:
        """路由到下一个 Agent"""
        return self.router.route(current_agent, state)
    
    def _finalize_output(self, state: GraphState) -> GraphState:
        """生成最终输出"""
        # 优先使用生成的内容
        generated = state.get("generated_content", {})
        if generated:
            content = generated.get("content", "")
            title = generated.get("title", "")
            tags = generated.get("tags", [])
            
            if title:
                final_output = f"【{title}】\n\n{content}"
            else:
                final_output = content
            
            if tags:
                final_output += "\n\n" + " ".join(f"#{tag}" for tag in tags)
            
            state["final_output"] = final_output
        else:
            # 没有生成内容，使用最后一个成功的输出
            for output in reversed(state.get("agent_outputs", [])):
                if output.get("success") and output.get("output"):
                    state["final_output"] = str(output["output"])
                    break
        
        return state
    
    def _build_result(self, state: GraphState) -> Dict[str, Any]:
        """构建返回结果"""
        return {
            "success": state["status"] == WorkflowStatus.COMPLETED,
            "status": state["status"].value,
            "output": state.get("final_output", ""),
            "generated_content": state.get("generated_content"),
            "review_result": state.get("review_result"),
            "agent_sequence": state.get("agent_sequence", []),
            "iteration_count": state.get("iteration_count", 0),
            "errors": state.get("errors", []),
            "metadata": {
                "thread_id": state.get("thread_id"),
                "user_id": state.get("user_id"),
                "created_at": state.get("created_at"),
                "completed_at": datetime.now().isoformat()
            }
        }
    
    async def _safe_callback(self, callback: Callable, *args) -> None:
        """安全执行回调"""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(*args)
            else:
                callback(*args)
        except Exception as e:
            print(f"Callback error: {e}")


class WorkflowBuilder:
    """
    工作流构建器
    提供流式 API 构建工作流
    """
    
    def __init__(self):
        self._max_iterations = 10
        self._enable_history = True
        self._custom_agents = {}
        self._custom_routes = []
        self._callbacks = {}
    
    def max_iterations(self, value: int) -> "WorkflowBuilder":
        """设置最大迭代次数"""
        self._max_iterations = value
        return self
    
    def enable_history(self, value: bool = True) -> "WorkflowBuilder":
        """启用历史记录"""
        self._enable_history = value
        return self
    
    def add_agent(self, name: str, agent: Any) -> "WorkflowBuilder":
        """添加自定义 Agent"""
        self._custom_agents[name] = agent
        return self
    
    def add_route(
        self,
        from_agent: str,
        condition: Callable,
        to_agent: str
    ) -> "WorkflowBuilder":
        """添加自定义路由"""
        self._custom_routes.append({
            "from": from_agent,
            "condition": condition,
            "to": to_agent
        })
        return self
    
    def on_agent_start(self, callback: Callable) -> "WorkflowBuilder":
        """设置 Agent 开始回调"""
        self._callbacks["on_agent_start"] = callback
        return self
    
    def on_agent_end(self, callback: Callable) -> "WorkflowBuilder":
        """设置 Agent 结束回调"""
        self._callbacks["on_agent_end"] = callback
        return self
    
    def on_workflow_end(self, callback: Callable) -> "WorkflowBuilder":
        """设置工作流结束回调"""
        self._callbacks["on_workflow_end"] = callback
        return self
    
    def build(self) -> AgentWorkflow:
        """构建工作流"""
        workflow = AgentWorkflow(
            max_iterations=self._max_iterations,
            enable_history=self._enable_history
        )
        
        # 添加自定义 Agent
        for name, agent in self._custom_agents.items():
            workflow.agents[name] = agent
        
        # 添加自定义路由
        for route in self._custom_routes:
            workflow.router.add_custom_route(
                route["from"],
                route["condition"],
                route["to"]
            )
        
        # 设置回调
        workflow.set_callbacks(**self._callbacks)
        
        return workflow


def create_default_workflow() -> AgentWorkflow:
    """创建默认工作流"""
    return WorkflowBuilder().build()
