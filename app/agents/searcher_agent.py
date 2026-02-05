"""
Searcher Agent（搜索员）
负责信息搜集、热点获取、素材收集
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
from app.core.base_skill import SkillResult


class SearcherAgent(BaseAgent):
    """
    搜索 Agent
    负责：
    1. 搜索网页信息
    2. 获取社交媒体热点
    3. 收集素材和参考资料
    4. 整理搜索结果
    """
    
    def __init__(
        self,
        llm_engine=None,
        memory_manager=None,
        skill_registry=None
    ):
        super().__init__(
            name="searcher",
            role=AgentRole.SEARCHER,
            description="负责信息搜集和热点获取的搜索 Agent",
            llm_engine=llm_engine or get_llm_engine(),
            memory_manager=memory_manager or get_memory_manager(),
            skill_registry=skill_registry or get_skill_registry()
        )
    
    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        return """你是一个专业的信息搜索助手，负责收集和整理信息。

## 你的职责
1. 根据用户需求确定搜索策略
2. 调用搜索工具获取信息
3. 筛选和整理搜索结果
4. 提取关键信息供后续使用

## 可用工具
- web_search: 网页搜索
- get_trending: 获取热点话题
- web_scrape: 抓取网页内容

## 输出格式
你需要输出 JSON 格式的搜索计划或结果：
```json
{
    "action": "search|summarize",
    "tool": "工具名称（如果 action 是 search）",
    "parameters": {
        "query": "搜索关键词",
        "其他参数": "值"
    },
    "summary": "搜索结果摘要（如果 action 是 summarize）",
    "key_points": ["关键点1", "关键点2"]
}
```

## 搜索策略
1. 先分析用户需求，确定搜索关键词
2. 选择合适的搜索工具
3. 如果需要多次搜索，分步执行
4. 整理结果时提取最相关的信息

## 注意事项
- 只输出 JSON，不要有其他内容
- 搜索结果要精简，突出重点
- 如果搜索无结果，说明原因并建议替代方案
"""
    
    async def execute(self, context: AgentContext) -> AgentResult:
        """执行搜索任务"""
        try:
            # 获取搜索参数
            params = context.get_variable("agent_parameters", {}).get("searcher", {})
            user_input = context.get_variable("user_input", "")
            
            # 确定搜索任务
            search_query = params.get("query", user_input)
            search_type = params.get("type", "general")  # general, trending, specific
            
            # 构建消息
            messages = [
                LLMMessage(role="system", content=self.system_prompt),
                LLMMessage(
                    role="user",
                    content=f"请帮我搜索以下内容：{search_query}\n搜索类型：{search_type}"
                )
            ]
            
            # 第一步：让 LLM 决定搜索策略
            response = await self.llm_engine.chat(messages)
            
            try:
                content = response.content.strip()
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]
                
                plan = json.loads(content)
            except json.JSONDecodeError:
                # 使用默认搜索计划
                plan = {
                    "action": "search",
                    "tool": "web_search",
                    "parameters": {"query": search_query, "num_results": 5}
                }
            
            # 第二步：执行搜索
            search_results = []
            
            if plan.get("action") == "search":
                tool_name = plan.get("tool", "web_search")
                tool_params = plan.get("parameters", {})
                
                # 调用技能
                skill_result = await self.skill_registry.execute_skill(
                    tool_name,
                    **tool_params
                )
                
                if skill_result.success:
                    search_results = skill_result.data
                else:
                    # 搜索失败，尝试获取热点作为备选
                    trending_result = await self.skill_registry.execute_skill(
                        "get_trending",
                        platform="general",
                        limit=5
                    )
                    if trending_result.success:
                        search_results = trending_result.data
            
            # 第三步：整理搜索结果
            summary_messages = [
                LLMMessage(role="system", content=self.system_prompt),
                LLMMessage(
                    role="user",
                    content=f"""请整理以下搜索结果，提取关键信息：

搜索查询：{search_query}
搜索结果：
{json.dumps(search_results, ensure_ascii=False, indent=2)}

请输出 JSON 格式的摘要，包含 action: "summarize"、summary 和 key_points。
"""
                )
            ]
            
            summary_response = await self.llm_engine.chat(summary_messages)
            
            try:
                summary_content = summary_response.content.strip()
                if "```json" in summary_content:
                    summary_content = summary_content.split("```json")[1].split("```")[0]
                elif "```" in summary_content:
                    summary_content = summary_content.split("```")[1].split("```")[0]
                
                summary = json.loads(summary_content)
            except json.JSONDecodeError:
                summary = {
                    "action": "summarize",
                    "summary": "搜索完成",
                    "key_points": [str(r) for r in search_results[:3]] if search_results else []
                }
            
            # 存储搜索结果到上下文
            output = {
                "query": search_query,
                "raw_results": search_results,
                "summary": summary.get("summary", ""),
                "key_points": summary.get("key_points", []),
                "result_count": len(search_results) if isinstance(search_results, list) else 0
            }
            
            context.set_variable("search_results", output)
            
            # 存储到记忆
            if output["summary"]:
                await self.memory_manager.store(
                    content=f"搜索「{search_query}」的结果：{output['summary']}",
                    memory_type=self.memory_manager.short_term.memory_type,
                    thread_id=context.thread_id,
                    metadata={"type": "search_result", "query": search_query}
                )
            
            return AgentResult.success_result(
                output=output,
                agent_name=self.name,
                metadata={
                    "query": search_query,
                    "result_count": output["result_count"],
                    "token_usage": response.usage
                }
            )
            
        except Exception as e:
            return AgentResult.failure_result(
                error=str(e),
                agent_name=self.name
            )
    
    async def search_trending(
        self,
        platform: str = "general",
        category: str = "all",
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        获取热点话题
        
        Args:
            platform: 平台名称
            category: 分类
            limit: 数量限制
            
        Returns:
            List[Dict]: 热点列表
        """
        result = await self.skill_registry.execute_skill(
            "get_trending",
            platform=platform,
            category=category,
            limit=limit
        )
        
        if result.success:
            return result.data
        return []
    
    async def search_web(
        self,
        query: str,
        num_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        网页搜索
        
        Args:
            query: 搜索关键词
            num_results: 结果数量
            
        Returns:
            List[Dict]: 搜索结果
        """
        result = await self.skill_registry.execute_skill(
            "web_search",
            query=query,
            num_results=num_results
        )
        
        if result.success:
            return result.data
        return []
