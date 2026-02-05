"""
Writer Agent（写手）
负责生成社交媒体文案和内容
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


class WriterAgent(BaseAgent):
    """
    写作 Agent
    负责：
    1. 根据素材生成文案
    2. 适配不同平台的风格
    3. 注入人设和语气
    4. 添加话题标签和表情
    """
    
    # 平台特性配置
    PLATFORM_CONFIGS = {
        "weibo": {
            "max_length": 2000,
            "style": "活泼、接地气",
            "features": ["话题标签", "表情", "@提及"],
            "tips": "适合热点话题讨论，可以加入互动问题"
        },
        "xiaohongshu": {
            "max_length": 1000,
            "style": "种草、分享、真诚",
            "features": ["标题党", "分段清晰", "表情丰富"],
            "tips": "开头要吸引人，内容要有干货，结尾要有互动"
        },
        "twitter": {
            "max_length": 280,
            "style": "简洁、有力",
            "features": ["hashtag", "简短有力"],
            "tips": "一句话说清楚，善用 hashtag"
        },
        "douyin": {
            "max_length": 500,
            "style": "口语化、有节奏感",
            "features": ["短句", "节奏感", "话题标签"],
            "tips": "适合配合视频，文案要有节奏感"
        },
        "general": {
            "max_length": 1000,
            "style": "通用",
            "features": ["清晰", "有条理"],
            "tips": "根据内容调整风格"
        }
    }
    
    # 人设模板
    PERSONA_TEMPLATES = {
        "professional": {
            "tone": "专业、权威、可信",
            "vocabulary": "使用行业术语，数据支撑",
            "style": "条理清晰，逻辑严密"
        },
        "friendly": {
            "tone": "亲切、随和、有温度",
            "vocabulary": "口语化，接地气",
            "style": "像朋友聊天一样自然"
        },
        "humorous": {
            "tone": "幽默、风趣、轻松",
            "vocabulary": "网络用语，梗和段子",
            "style": "轻松愉快，让人会心一笑"
        },
        "inspirational": {
            "tone": "励志、正能量、鼓舞人心",
            "vocabulary": "积极向上的词汇",
            "style": "富有感染力，引发共鸣"
        }
    }
    
    def __init__(
        self,
        llm_engine=None,
        memory_manager=None,
        skill_registry=None
    ):
        super().__init__(
            name="writer",
            role=AgentRole.WRITER,
            description="负责生成社交媒体文案的写作 Agent",
            llm_engine=llm_engine or get_llm_engine(),
            memory_manager=memory_manager or get_memory_manager(),
            skill_registry=skill_registry or get_skill_registry()
        )
    
    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        return """你是一个专业的社交媒体文案写手，擅长创作吸引人的内容。

## 你的职责
1. 根据主题和素材创作文案
2. 适配目标平台的风格和限制
3. 融入指定的人设和语气
4. 添加合适的话题标签和表情

## 写作原则
1. **开头吸引人**：前几句话决定用户是否继续阅读
2. **内容有价值**：提供信息、观点或情感价值
3. **结尾有互动**：引导用户点赞、评论、转发
4. **符合平台调性**：不同平台有不同的内容风格

## 输出格式
```json
{
    "title": "标题（如果平台需要）",
    "content": "正文内容",
    "tags": ["话题标签1", "话题标签2"],
    "platform": "目标平台",
    "word_count": 字数,
    "highlights": ["亮点1", "亮点2"]
}
```

## 注意事项
- 只输出 JSON，不要有其他内容
- 内容要原创，不能直接复制素材
- 注意字数限制
- 话题标签要相关且热门
"""
    
    async def execute(self, context: AgentContext) -> AgentResult:
        """执行写作任务"""
        try:
            # 获取参数
            params = context.get_variable("agent_parameters", {}).get("writer", {})
            user_input = context.get_variable("user_input", "")
            search_results = context.get_variable("search_results", {})
            
            # 提取写作参数
            topic = params.get("topic", user_input)
            platform = params.get("platform", "general")
            persona = params.get("persona", "friendly")
            style = params.get("style")
            
            # 获取平台配置
            platform_config = self.PLATFORM_CONFIGS.get(
                platform,
                self.PLATFORM_CONFIGS["general"]
            )
            
            # 获取人设配置
            persona_config = self.PERSONA_TEMPLATES.get(
                persona,
                self.PERSONA_TEMPLATES["friendly"]
            )
            
            # 获取用户偏好
            user_profile = None
            if context.user_id:
                user_profile = await self.memory_manager.get_user_profile(context.user_id)
            
            # 构建写作提示
            writing_prompt = self._build_writing_prompt(
                topic=topic,
                platform=platform,
                platform_config=platform_config,
                persona_config=persona_config,
                search_results=search_results,
                user_profile=user_profile,
                custom_style=style
            )
            
            # 构建消息
            messages = [
                LLMMessage(role="system", content=self.system_prompt),
                LLMMessage(role="user", content=writing_prompt)
            ]
            
            # 调用 LLM 生成内容
            response = await self.llm_engine.chat(messages)
            
            # 解析响应
            try:
                content = response.content.strip()
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0]
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0]
                
                result = json.loads(content)
            except json.JSONDecodeError:
                # 如果解析失败，将整个响应作为内容
                result = {
                    "title": "",
                    "content": response.content,
                    "tags": [],
                    "platform": platform,
                    "word_count": len(response.content),
                    "highlights": []
                }
            
            # 验证内容长度
            max_length = platform_config["max_length"]
            if len(result.get("content", "")) > max_length:
                # 内容过长，需要压缩
                result = await self._compress_content(result, max_length)
            
            # 存储到上下文
            context.set_variable("generated_content", result)
            
            # 存储到记忆
            await self.memory_manager.store(
                content=f"为「{topic}」生成的{platform}文案：{result.get('content', '')[:100]}...",
                memory_type=self.memory_manager.short_term.memory_type,
                thread_id=context.thread_id,
                metadata={
                    "type": "generated_content",
                    "platform": platform,
                    "topic": topic
                }
            )
            
            return AgentResult.success_result(
                output=result,
                agent_name=self.name,
                metadata={
                    "platform": platform,
                    "persona": persona,
                    "word_count": result.get("word_count", 0),
                    "token_usage": response.usage
                }
            )
            
        except Exception as e:
            return AgentResult.failure_result(
                error=str(e),
                agent_name=self.name
            )
    
    def _build_writing_prompt(
        self,
        topic: str,
        platform: str,
        platform_config: Dict,
        persona_config: Dict,
        search_results: Dict,
        user_profile: Optional[Any],
        custom_style: Optional[str]
    ) -> str:
        """构建写作提示"""
        prompt_parts = []
        
        # 主题
        prompt_parts.append(f"## 写作主题\n{topic}")
        
        # 平台要求
        prompt_parts.append(f"""## 平台要求
- 平台：{platform}
- 字数限制：{platform_config['max_length']} 字以内
- 风格：{platform_config['style']}
- 特点：{', '.join(platform_config['features'])}
- 建议：{platform_config['tips']}""")
        
        # 人设要求
        prompt_parts.append(f"""## 人设要求
- 语气：{persona_config['tone']}
- 用词：{persona_config['vocabulary']}
- 风格：{persona_config['style']}""")
        
        # 自定义风格
        if custom_style:
            prompt_parts.append(f"## 特别要求\n{custom_style}")
        
        # 素材（如果有搜索结果）
        if search_results:
            summary = search_results.get("summary", "")
            key_points = search_results.get("key_points", [])
            
            if summary or key_points:
                material = f"## 参考素材\n摘要：{summary}"
                if key_points:
                    material += f"\n关键点：\n" + "\n".join(f"- {p}" for p in key_points)
                prompt_parts.append(material)
        
        # 用户偏好
        if user_profile:
            if user_profile.writing_style:
                prompt_parts.append(f"## 用户偏好风格\n{user_profile.writing_style}")
            if user_profile.constraints:
                prompt_parts.append(f"## 内容约束\n" + "\n".join(f"- {c}" for c in user_profile.constraints))
        
        prompt_parts.append("\n请根据以上要求创作文案，输出 JSON 格式。")
        
        return "\n\n".join(prompt_parts)
    
    async def _compress_content(
        self,
        result: Dict,
        max_length: int
    ) -> Dict:
        """压缩过长的内容"""
        content = result.get("content", "")
        
        if len(content) <= max_length:
            return result
        
        # 使用 LLM 压缩
        compress_prompt = f"""请将以下内容压缩到 {max_length} 字以内，保留核心信息：

{content}

输出 JSON 格式：
{{"content": "压缩后的内容"}}
"""
        
        messages = [
            LLMMessage(role="system", content="你是一个文案编辑，擅长精简内容。"),
            LLMMessage(role="user", content=compress_prompt)
        ]
        
        response = await self.llm_engine.chat(messages)
        
        try:
            compressed = json.loads(response.content)
            result["content"] = compressed.get("content", content[:max_length])
            result["word_count"] = len(result["content"])
            result["compressed"] = True
        except:
            result["content"] = content[:max_length]
            result["word_count"] = max_length
        
        return result
    
    async def generate_variations(
        self,
        content: str,
        count: int = 3,
        platform: str = "general"
    ) -> List[str]:
        """
        生成内容变体
        
        Args:
            content: 原始内容
            count: 变体数量
            platform: 目标平台
            
        Returns:
            List[str]: 变体列表
        """
        prompt = f"""请为以下内容生成 {count} 个不同的变体版本，适合 {platform} 平台：

原始内容：
{content}

输出 JSON 格式：
{{"variations": ["变体1", "变体2", "变体3"]}}
"""
        
        messages = [
            LLMMessage(role="system", content=self.system_prompt),
            LLMMessage(role="user", content=prompt)
        ]
        
        response = await self.llm_engine.chat(messages)
        
        try:
            result = json.loads(response.content)
            return result.get("variations", [])
        except:
            return []
