"""
Reviewer Agent（审核员）
负责内容校验、质量评估和优化建议
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
from app.config import settings


class ReviewerAgent(BaseAgent):
    """
    审核 Agent
    负责：
    1. 内容质量评估
    2. 合规性检查
    3. 优化建议
    4. 最终审批
    """
    
    # 评估维度
    REVIEW_DIMENSIONS = {
        "quality": {
            "name": "内容质量",
            "weight": 0.3,
            "criteria": ["原创性", "可读性", "信息价值", "逻辑性"]
        },
        "engagement": {
            "name": "互动潜力",
            "weight": 0.25,
            "criteria": ["吸引力", "话题性", "互动引导", "情感共鸣"]
        },
        "compliance": {
            "name": "合规性",
            "weight": 0.25,
            "criteria": ["无敏感词", "无违规内容", "符合平台规范", "无版权问题"]
        },
        "style": {
            "name": "风格匹配",
            "weight": 0.2,
            "criteria": ["人设一致", "语气恰当", "平台适配", "品牌调性"]
        }
    }
    
    def __init__(
        self,
        llm_engine=None,
        memory_manager=None,
        skill_registry=None,
        review_threshold: float = None
    ):
        super().__init__(
            name="reviewer",
            role=AgentRole.REVIEWER,
            description="负责内容审核和质量评估的审核 Agent",
            llm_engine=llm_engine or get_llm_engine(),
            memory_manager=memory_manager or get_memory_manager(),
            skill_registry=skill_registry or get_skill_registry()
        )
        self.review_threshold = review_threshold or settings.REVIEW_THRESHOLD
    
    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        dimensions_desc = "\n".join([
            f"- {dim['name']}（权重 {dim['weight']}）：{', '.join(dim['criteria'])}"
            for dim in self.REVIEW_DIMENSIONS.values()
        ])
        
        return f"""你是一个专业的内容审核员，负责评估社交媒体内容的质量和合规性。

## 评估维度
{dimensions_desc}

## 你的职责
1. 对内容进行多维度评估
2. 识别潜在问题和风险
3. 提供具体的优化建议
4. 给出最终审核结论

## 输出格式
```json
{{
    "scores": {{
        "quality": 0.0-1.0,
        "engagement": 0.0-1.0,
        "compliance": 0.0-1.0,
        "style": 0.0-1.0
    }},
    "overall_score": 0.0-1.0,
    "passed": true/false,
    "issues": [
        {{"type": "问题类型", "description": "问题描述", "severity": "high/medium/low"}}
    ],
    "suggestions": [
        {{"aspect": "优化方面", "suggestion": "具体建议"}}
    ],
    "summary": "审核总结"
}}
```

## 评分标准
- 0.9-1.0：优秀，可直接发布
- 0.8-0.9：良好，建议小幅优化
- 0.7-0.8：合格，需要一定修改
- 0.6-0.7：勉强，需要较大修改
- 0.6以下：不合格，需要重写

## 注意事项
- 只输出 JSON，不要有其他内容
- 评分要客观公正
- 问题要具体指出位置
- 建议要可操作
"""
    
    async def execute(self, context: AgentContext) -> AgentResult:
        """执行审核任务"""
        try:
            # 获取待审核内容
            generated_content = context.get_variable("generated_content", {})
            
            if not generated_content:
                return AgentResult.failure_result(
                    error="没有找到待审核的内容",
                    agent_name=self.name
                )
            
            content = generated_content.get("content", "")
            platform = generated_content.get("platform", "general")
            
            # 第一步：使用技能进行硬校验
            validation_result = await self._hard_validation(content, platform)
            
            # 第二步：使用 LLM 进行软评估
            llm_review = await self._llm_review(generated_content, context)
            
            # 合并结果
            final_result = self._merge_results(validation_result, llm_review)
            
            # 判断是否通过
            final_result["passed"] = final_result["overall_score"] >= self.review_threshold
            
            # 如果不通过，决定是否需要重写
            if not final_result["passed"]:
                final_result["action"] = self._decide_action(final_result)
            else:
                final_result["action"] = "approve"
            
            # 存储到上下文
            context.set_variable("review_result", final_result)
            
            # 存储到记忆
            await self.memory_manager.store(
                content=f"内容审核结果：得分 {final_result['overall_score']:.2f}，{'通过' if final_result['passed'] else '未通过'}",
                memory_type=self.memory_manager.short_term.memory_type,
                thread_id=context.thread_id,
                metadata={
                    "type": "review_result",
                    "score": final_result["overall_score"],
                    "passed": final_result["passed"]
                }
            )
            
            return AgentResult.success_result(
                output=final_result,
                agent_name=self.name,
                metadata={
                    "overall_score": final_result["overall_score"],
                    "passed": final_result["passed"],
                    "action": final_result["action"]
                }
            )
            
        except Exception as e:
            return AgentResult.failure_result(
                error=str(e),
                agent_name=self.name
            )
    
    async def _hard_validation(
        self,
        content: str,
        platform: str
    ) -> Dict[str, Any]:
        """硬校验（使用技能）"""
        result = {
            "issues": [],
            "compliance_score": 1.0
        }
        
        # 调用内容校验技能
        validation = await self.skill_registry.execute_skill(
            "validate_content",
            content=content,
            platform=platform,
            check_sensitive=True
        )
        
        if validation.success:
            data = validation.data
            
            if not data.get("is_valid", True):
                result["compliance_score"] = 0.5
            
            for issue in data.get("issues", []):
                result["issues"].append({
                    "type": "compliance",
                    "description": issue,
                    "severity": "high"
                })
            
            for warning in data.get("warnings", []):
                result["issues"].append({
                    "type": "warning",
                    "description": warning,
                    "severity": "medium"
                })
        
        return result
    
    async def _llm_review(
        self,
        generated_content: Dict,
        context: AgentContext
    ) -> Dict[str, Any]:
        """LLM 软评估"""
        content = generated_content.get("content", "")
        platform = generated_content.get("platform", "general")
        tags = generated_content.get("tags", [])
        
        # 获取用户偏好
        user_profile = None
        if context.user_id:
            user_profile = await self.memory_manager.get_user_profile(context.user_id)
        
        # 构建审核提示
        review_prompt = f"""请审核以下社交媒体内容：

## 待审核内容
平台：{platform}
内容：
{content}

话题标签：{', '.join(tags) if tags else '无'}
"""
        
        if user_profile and user_profile.constraints:
            review_prompt += f"\n## 用户约束\n" + "\n".join(f"- {c}" for c in user_profile.constraints)
        
        review_prompt += "\n\n请按照评估维度进行评分，并输出 JSON 格式的审核结果。"
        
        messages = [
            LLMMessage(role="system", content=self.system_prompt),
            LLMMessage(role="user", content=review_prompt)
        ]
        
        response = await self.llm_engine.chat(messages)
        
        try:
            content = response.content.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            return json.loads(content)
        except json.JSONDecodeError:
            # 返回默认评估
            return {
                "scores": {
                    "quality": 0.7,
                    "engagement": 0.7,
                    "compliance": 0.8,
                    "style": 0.7
                },
                "overall_score": 0.72,
                "issues": [],
                "suggestions": [],
                "summary": "自动评估完成"
            }
    
    def _merge_results(
        self,
        validation_result: Dict,
        llm_review: Dict
    ) -> Dict[str, Any]:
        """合并校验结果"""
        # 合并问题列表
        all_issues = validation_result.get("issues", []) + llm_review.get("issues", [])
        
        # 调整合规性分数
        scores = llm_review.get("scores", {})
        if validation_result.get("compliance_score", 1.0) < 1.0:
            scores["compliance"] = min(
                scores.get("compliance", 0.8),
                validation_result["compliance_score"]
            )
        
        # 计算加权总分
        overall_score = sum(
            scores.get(dim, 0.7) * config["weight"]
            for dim, config in self.REVIEW_DIMENSIONS.items()
        )
        
        return {
            "scores": scores,
            "overall_score": round(overall_score, 2),
            "issues": all_issues,
            "suggestions": llm_review.get("suggestions", []),
            "summary": llm_review.get("summary", "")
        }
    
    def _decide_action(self, result: Dict) -> str:
        """决定后续动作"""
        score = result["overall_score"]
        high_severity_issues = [
            i for i in result.get("issues", [])
            if i.get("severity") == "high"
        ]
        
        if high_severity_issues:
            return "rewrite"  # 有严重问题，需要重写
        elif score >= 0.6:
            return "revise"  # 分数尚可，修改即可
        else:
            return "rewrite"  # 分数太低，需要重写
    
    async def suggest_improvements(
        self,
        content: str,
        issues: List[Dict]
    ) -> str:
        """
        生成改进后的内容
        
        Args:
            content: 原始内容
            issues: 问题列表
            
        Returns:
            str: 改进后的内容
        """
        issues_desc = "\n".join([
            f"- {i['description']}"
            for i in issues
        ])
        
        prompt = f"""请根据以下问题改进内容：

原始内容：
{content}

存在的问题：
{issues_desc}

请输出改进后的内容，只输出内容本身，不要有其他说明。
"""
        
        messages = [
            LLMMessage(
                role="system",
                content="你是一个内容优化专家，擅长改进社交媒体文案。"
            ),
            LLMMessage(role="user", content=prompt)
        ]
        
        response = await self.llm_engine.chat(messages)
        return response.content.strip()
