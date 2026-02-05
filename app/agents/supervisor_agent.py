"""
Supervisor Agent（调度员）
负责接收用户指令，分析意图，决定启动哪个 Agent
"""

import json
from typing import Any, Dict, List, Optional

from app.core.base_agent import (
    BaseAgent,
    AgentRole,
    AgentStatus,
    AgentContext,
    AgentResult
)
from app.services.llm_engine import LLMMessage, get_llm_engine
from app.memory.manager import get_memory_manager
from app.skills.registry import get_skill_registry


class SupervisorAgent(BaseAgent):
    """
    调度员 Agent
    负责：
    1. 解析用户意图
    2. 决定任务路由
    3. 协调其他 Agent 的执行
    4. 汇总最终结果
    """
    
    def __init__(
        self,
        llm_engine=None,
        memory_manager=None,
        skill_registry=None
    ):
        super().__init__(
            name="supervisor",
            role=AgentRole.SUPERVISOR,
            description="负责任务调度和协调的主控 Agent",
            llm_engine=llm_engine or get_llm_engine(),
            memory_manager=memory_manager or get_memory_manager(),
            skill_registry=skill_registry or get_skill_registry()
        )
        
        # 可用的子 Agent 列表
        self.available_agents = {
            "searcher": "搜索 Agent - 负责信息搜集和热点获取",
            "writer": "写作 Agent - 负责生成社交媒体文案",
            "reviewer": "审核 Agent - 负责内容校验和优化"
        }
    
    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        agents_desc = "\n".join([
            f"- {name}: {desc}"
            for name, desc in self.available_agents.items()
        ])
        
        return f"""你是一个智能任务调度员，负责分析用户的请求并决定如何处理。

## 你的职责
1. 理解用户的真实意图
2. 判断需要调用哪些 Agent 来完成任务
3. 确定 Agent 的执行顺序
4. 提取关键参数传递给下游 Agent

## 可用的 Agent
{agents_desc}

## 输出格式
你必须以 JSON 格式输出决策结果：
```json
{{
    "intent": "用户意图的简短描述",
    "agents": ["需要调用的 Agent 列表，按执行顺序排列"],
    "parameters": {{
        "agent_name": {{
            "param1": "value1",
            "param2": "value2"
        }}
    }},
    "reasoning": "你的决策理由"
}}
```

## 决策规则
1. 如果用户想要获取热点或搜索信息 → 调用 searcher
2. 如果用户想要生成文案或内容 → 先调用 searcher（如需素材），再调用 writer
3. 如果用户想要发布内容 → 调用 writer，然后 reviewer
4. 复杂任务可能需要多个 Agent 协作

## 注意事项
- 只输出 JSON，不要有其他内容
- 确保 JSON 格式正确
- agents 数组不能为空
"""
    
    async def execute(self, context: AgentContext) -> AgentResult:
        """执行调度逻辑"""
        try:
            # 获取用户输入
            user_input = context.get_variable("user_input", "")
            if not user_input:
                # 从最后一条用户消息获取
                for msg in reversed(context.messages):
                    if msg.role == "user":
                        user_input = msg.content
                        break
            
            if not user_input:
                return AgentResult.failure_result(
                    error="没有找到用户输入",
                    agent_name=self.name
                )
            
            # 获取相关上下文
            memory_context = await self.memory_manager.get_context(
                query_text=user_input,
                user_id=context.user_id,
                thread_id=context.thread_id,
                max_length=500
            )
            
            # 构建消息
            messages = [
                LLMMessage(role="system", content=self.system_prompt),
            ]
            
            if memory_context:
                messages.append(LLMMessage(
                    role="system",
                    content=f"## 相关上下文\n{memory_context}"
                ))
            
            messages.append(LLMMessage(role="user", content=user_input))
            
            # 调用 LLM
            response = await self.llm_engine.chat(messages)
            
            # 解析响应
            try:
                # 尝试提取 JSON
                content = response.content.strip()
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]
                
                decision = json.loads(content)
            except json.JSONDecodeError as e:
                # 如果解析失败，使用默认决策
                decision = {
                    "intent": "无法解析用户意图",
                    "agents": ["writer"],
                    "parameters": {
                        "writer": {"content": user_input}
                    },
                    "reasoning": f"JSON 解析失败，使用默认路由: {str(e)}"
                }
            
            # 验证决策
            if not decision.get("agents"):
                decision["agents"] = ["writer"]
            
            # 存储决策到上下文
            context.set_variable("supervisor_decision", decision)
            context.set_variable("next_agents", decision["agents"])
            context.set_variable("agent_parameters", decision.get("parameters", {}))
            
            # 存储到短期记忆
            await self.memory_manager.store_task_state(
                thread_id=context.thread_id,
                state={
                    "user_input": user_input,
                    "decision": decision,
                    "status": "dispatched"
                }
            )
            
            return AgentResult.success_result(
                output=decision,
                agent_name=self.name,
                metadata={
                    "intent": decision.get("intent"),
                    "agents": decision.get("agents"),
                    "token_usage": response.usage
                }
            )
            
        except Exception as e:
            return AgentResult.failure_result(
                error=str(e),
                agent_name=self.name
            )
    
    async def route_to_agent(
        self,
        agent_name: str,
        context: AgentContext
    ) -> str:
        """
        根据决策路由到下一个 Agent
        
        Args:
            agent_name: 目标 Agent 名称
            context: 执行上下文
            
        Returns:
            str: 下一个 Agent 的名称
        """
        decision = context.get_variable("supervisor_decision", {})
        agents = decision.get("agents", [])
        
        if agent_name in agents:
            idx = agents.index(agent_name)
            if idx < len(agents) - 1:
                return agents[idx + 1]
        
        return "end"  # 没有下一个 Agent
    
    def get_agent_parameters(
        self,
        agent_name: str,
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        获取指定 Agent 的参数
        
        Args:
            agent_name: Agent 名称
            context: 执行上下文
            
        Returns:
            Dict: Agent 参数
        """
        parameters = context.get_variable("agent_parameters", {})
        return parameters.get(agent_name, {})
