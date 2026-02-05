"""
社交媒体工具技能
提供发帖、评论、私信等社交媒体操作功能
"""

import asyncio
import httpx
from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum

from app.core.base_skill import (
    BaseSkill,
    SkillCategory,
    SkillParameter,
    SkillDefinition,
    SkillResult,
    skill
)
from app.config import settings


class SocialPlatform(str, Enum):
    """社交平台枚举"""
    TWITTER = "twitter"
    WEIBO = "weibo"
    XIAOHONGSHU = "xiaohongshu"
    DOUYIN = "douyin"
    WECHAT = "wechat"


class PostStatus(str, Enum):
    """帖子状态枚举"""
    DRAFT = "draft"
    PENDING = "pending"
    PUBLISHED = "published"
    FAILED = "failed"
    DELETED = "deleted"


class SocialPostSkill(BaseSkill):
    """社交媒体发帖技能"""
    
    def __init__(self):
        super().__init__()
        self.client = httpx.AsyncClient(timeout=30)
    
    def _build_definition(self) -> SkillDefinition:
        return SkillDefinition(
            name="social_post",
            description="在社交媒体平台发布内容",
            category=SkillCategory.SOCIAL,
            parameters=[
                SkillParameter(
                    name="platform",
                    type="string",
                    description="目标平台：twitter、weibo、xiaohongshu、douyin",
                    required=True,
                    enum=["twitter", "weibo", "xiaohongshu", "douyin"]
                ),
                SkillParameter(
                    name="content",
                    type="string",
                    description="发布内容",
                    required=True
                ),
                SkillParameter(
                    name="media_urls",
                    type="array",
                    description="媒体文件 URL 列表（图片/视频）",
                    required=False
                ),
                SkillParameter(
                    name="tags",
                    type="array",
                    description="话题标签列表",
                    required=False
                ),
                SkillParameter(
                    name="schedule_time",
                    type="string",
                    description="定时发布时间（ISO 格式）",
                    required=False
                )
            ],
            returns="Dict - 发布结果",
            requires_auth=True
        )
    
    async def execute(self, **kwargs) -> SkillResult:
        """执行发帖操作"""
        platform = kwargs.get("platform", "")
        content = kwargs.get("content", "")
        media_urls = kwargs.get("media_urls", [])
        tags = kwargs.get("tags", [])
        schedule_time = kwargs.get("schedule_time")
        
        if not platform:
            return SkillResult.failure_result("请指定发布平台")
        
        if not content:
            return SkillResult.failure_result("发布内容不能为空")
        
        try:
            # 根据平台调用不同的 API
            if platform == SocialPlatform.TWITTER.value:
                result = await self._post_to_twitter(content, media_urls, tags)
            elif platform == SocialPlatform.WEIBO.value:
                result = await self._post_to_weibo(content, media_urls, tags)
            elif platform == SocialPlatform.XIAOHONGSHU.value:
                result = await self._post_to_xiaohongshu(content, media_urls, tags)
            else:
                # 模拟发布
                result = self._mock_post(platform, content, media_urls, tags)
            
            return SkillResult.success_result(
                data=result,
                metadata={"platform": platform, "content_length": len(content)}
            )
        except Exception as e:
            return SkillResult.failure_result(f"发布失败: {str(e)}")
    
    async def _post_to_twitter(
        self,
        content: str,
        media_urls: List[str],
        tags: List[str]
    ) -> Dict[str, Any]:
        """发布到 Twitter"""
        # 实际项目中应该使用 Twitter API
        # 这里返回模拟结果
        return {
            "platform": "twitter",
            "post_id": f"tw_{datetime.now().timestamp()}",
            "status": PostStatus.PUBLISHED.value,
            "url": "https://twitter.com/user/status/123456789",
            "created_at": datetime.now().isoformat()
        }
    
    async def _post_to_weibo(
        self,
        content: str,
        media_urls: List[str],
        tags: List[str]
    ) -> Dict[str, Any]:
        """发布到微博"""
        return {
            "platform": "weibo",
            "post_id": f"wb_{datetime.now().timestamp()}",
            "status": PostStatus.PUBLISHED.value,
            "url": "https://weibo.com/123456789/AbCdEfG",
            "created_at": datetime.now().isoformat()
        }
    
    async def _post_to_xiaohongshu(
        self,
        content: str,
        media_urls: List[str],
        tags: List[str]
    ) -> Dict[str, Any]:
        """发布到小红书"""
        return {
            "platform": "xiaohongshu",
            "post_id": f"xhs_{datetime.now().timestamp()}",
            "status": PostStatus.PUBLISHED.value,
            "url": "https://www.xiaohongshu.com/explore/123456789",
            "created_at": datetime.now().isoformat()
        }
    
    def _mock_post(
        self,
        platform: str,
        content: str,
        media_urls: List[str],
        tags: List[str]
    ) -> Dict[str, Any]:
        """模拟发布（用于测试）"""
        return {
            "platform": platform,
            "post_id": f"mock_{datetime.now().timestamp()}",
            "status": PostStatus.PUBLISHED.value,
            "content_preview": content[:50] + "..." if len(content) > 50 else content,
            "media_count": len(media_urls),
            "tags": tags,
            "created_at": datetime.now().isoformat(),
            "note": "这是模拟发布结果"
        }


class SocialCommentSkill(BaseSkill):
    """社交媒体评论技能"""
    
    def __init__(self):
        super().__init__()
    
    def _build_definition(self) -> SkillDefinition:
        return SkillDefinition(
            name="social_comment",
            description="在社交媒体帖子下发表评论",
            category=SkillCategory.SOCIAL,
            parameters=[
                SkillParameter(
                    name="platform",
                    type="string",
                    description="目标平台",
                    required=True,
                    enum=["twitter", "weibo", "xiaohongshu", "douyin"]
                ),
                SkillParameter(
                    name="post_id",
                    type="string",
                    description="帖子 ID",
                    required=True
                ),
                SkillParameter(
                    name="content",
                    type="string",
                    description="评论内容",
                    required=True
                ),
                SkillParameter(
                    name="reply_to",
                    type="string",
                    description="回复的评论 ID（可选）",
                    required=False
                )
            ],
            returns="Dict - 评论结果",
            requires_auth=True
        )
    
    async def execute(self, **kwargs) -> SkillResult:
        """执行评论操作"""
        platform = kwargs.get("platform", "")
        post_id = kwargs.get("post_id", "")
        content = kwargs.get("content", "")
        reply_to = kwargs.get("reply_to")
        
        if not all([platform, post_id, content]):
            return SkillResult.failure_result("缺少必要参数")
        
        try:
            # 模拟评论操作
            result = {
                "platform": platform,
                "post_id": post_id,
                "comment_id": f"comment_{datetime.now().timestamp()}",
                "content": content,
                "reply_to": reply_to,
                "status": "published",
                "created_at": datetime.now().isoformat()
            }
            
            return SkillResult.success_result(data=result)
        except Exception as e:
            return SkillResult.failure_result(f"评论失败: {str(e)}")


class SocialAnalyticsSkill(BaseSkill):
    """社交媒体数据分析技能"""
    
    def __init__(self):
        super().__init__()
    
    def _build_definition(self) -> SkillDefinition:
        return SkillDefinition(
            name="social_analytics",
            description="获取社交媒体帖子的数据分析",
            category=SkillCategory.SOCIAL,
            parameters=[
                SkillParameter(
                    name="platform",
                    type="string",
                    description="目标平台",
                    required=True,
                    enum=["twitter", "weibo", "xiaohongshu", "douyin"]
                ),
                SkillParameter(
                    name="post_id",
                    type="string",
                    description="帖子 ID（可选，不填则获取账号整体数据）",
                    required=False
                ),
                SkillParameter(
                    name="metrics",
                    type="array",
                    description="要获取的指标：views、likes、comments、shares、followers",
                    required=False,
                    default=["views", "likes", "comments", "shares"]
                ),
                SkillParameter(
                    name="time_range",
                    type="string",
                    description="时间范围：day、week、month",
                    required=False,
                    default="day"
                )
            ],
            returns="Dict - 数据分析结果"
        )
    
    async def execute(self, **kwargs) -> SkillResult:
        """获取数据分析"""
        platform = kwargs.get("platform", "")
        post_id = kwargs.get("post_id")
        metrics = kwargs.get("metrics", ["views", "likes", "comments", "shares"])
        time_range = kwargs.get("time_range", "day")
        
        if not platform:
            return SkillResult.failure_result("请指定平台")
        
        try:
            # 模拟数据分析结果
            import random
            
            result = {
                "platform": platform,
                "post_id": post_id,
                "time_range": time_range,
                "metrics": {},
                "generated_at": datetime.now().isoformat()
            }
            
            for metric in metrics:
                if metric == "views":
                    result["metrics"]["views"] = random.randint(1000, 100000)
                elif metric == "likes":
                    result["metrics"]["likes"] = random.randint(100, 10000)
                elif metric == "comments":
                    result["metrics"]["comments"] = random.randint(10, 1000)
                elif metric == "shares":
                    result["metrics"]["shares"] = random.randint(5, 500)
                elif metric == "followers":
                    result["metrics"]["followers"] = random.randint(1000, 50000)
            
            # 计算互动率
            if "views" in result["metrics"] and result["metrics"]["views"] > 0:
                engagement = (
                    result["metrics"].get("likes", 0) +
                    result["metrics"].get("comments", 0) * 2 +
                    result["metrics"].get("shares", 0) * 3
                ) / result["metrics"]["views"] * 100
                result["metrics"]["engagement_rate"] = round(engagement, 2)
            
            return SkillResult.success_result(data=result)
        except Exception as e:
            return SkillResult.failure_result(f"获取数据失败: {str(e)}")


class ContentValidatorSkill(BaseSkill):
    """内容校验技能"""
    
    def __init__(self):
        super().__init__()
        # 敏感词列表（示例）
        self.sensitive_words = [
            "违禁词1", "违禁词2", "敏感词"
        ]
        # 平台字数限制
        self.platform_limits = {
            "twitter": 280,
            "weibo": 2000,
            "xiaohongshu": 1000,
            "douyin": 500
        }
    
    def _build_definition(self) -> SkillDefinition:
        return SkillDefinition(
            name="validate_content",
            description="校验社交媒体内容是否符合平台规范",
            category=SkillCategory.SOCIAL,
            parameters=[
                SkillParameter(
                    name="content",
                    type="string",
                    description="要校验的内容",
                    required=True
                ),
                SkillParameter(
                    name="platform",
                    type="string",
                    description="目标平台",
                    required=False,
                    default="general"
                ),
                SkillParameter(
                    name="check_sensitive",
                    type="boolean",
                    description="是否检查敏感词",
                    required=False,
                    default=True
                )
            ],
            returns="Dict - 校验结果"
        )
    
    async def execute(self, **kwargs) -> SkillResult:
        """执行内容校验"""
        content = kwargs.get("content", "")
        platform = kwargs.get("platform", "general")
        check_sensitive = kwargs.get("check_sensitive", True)
        
        if not content:
            return SkillResult.failure_result("内容不能为空")
        
        issues = []
        warnings = []
        
        # 检查字数限制
        content_length = len(content)
        if platform in self.platform_limits:
            limit = self.platform_limits[platform]
            if content_length > limit:
                issues.append(f"内容超出 {platform} 平台字数限制（{content_length}/{limit}）")
            elif content_length > limit * 0.9:
                warnings.append(f"内容接近字数限制（{content_length}/{limit}）")
        
        # 检查敏感词
        found_sensitive = []
        if check_sensitive:
            for word in self.sensitive_words:
                if word in content:
                    found_sensitive.append(word)
            if found_sensitive:
                issues.append(f"包含敏感词: {', '.join(found_sensitive)}")
        
        # 检查是否包含链接
        import re
        urls = re.findall(r'https?://\S+', content)
        if urls:
            warnings.append(f"内容包含 {len(urls)} 个链接，部分平台可能限流")
        
        # 检查话题标签
        hashtags = re.findall(r'#\w+', content)
        if len(hashtags) > 10:
            warnings.append("话题标签过多，建议控制在 10 个以内")
        
        # 检查 @ 提及
        mentions = re.findall(r'@\w+', content)
        if len(mentions) > 5:
            warnings.append("@ 提及过多，可能被判定为垃圾信息")
        
        is_valid = len(issues) == 0
        
        result = {
            "is_valid": is_valid,
            "content_length": content_length,
            "issues": issues,
            "warnings": warnings,
            "stats": {
                "hashtags": len(hashtags),
                "mentions": len(mentions),
                "urls": len(urls)
            }
        }
        
        return SkillResult.success_result(data=result)


# 使用装饰器定义的技能函数
@skill(
    name="format_social_content",
    description="格式化社交媒体内容，添加标签和表情",
    category=SkillCategory.SOCIAL,
    parameters=[
        SkillParameter(
            name="content",
            type="string",
            description="原始内容",
            required=True
        ),
        SkillParameter(
            name="style",
            type="string",
            description="风格：formal（正式）、casual（休闲）、humorous（幽默）",
            required=False,
            default="casual"
        ),
        SkillParameter(
            name="add_emoji",
            type="boolean",
            description="是否添加表情",
            required=False,
            default=True
        )
    ]
)
async def format_social_content(
    content: str,
    style: str = "casual",
    add_emoji: bool = True
) -> SkillResult:
    """格式化社交媒体内容"""
    
    # 风格对应的表情
    style_emojis = {
        "formal": ["📌", "💡", "📊", "✅"],
        "casual": ["😊", "🎉", "💪", "🔥", "✨"],
        "humorous": ["😂", "🤣", "😜", "🙈", "💯"]
    }
    
    formatted = content
    
    if add_emoji:
        import random
        emojis = style_emojis.get(style, style_emojis["casual"])
        # 在开头和结尾添加表情
        formatted = f"{random.choice(emojis)} {formatted} {random.choice(emojis)}"
    
    return SkillResult.success_result({
        "original": content,
        "formatted": formatted,
        "style": style,
        "length": len(formatted)
    })
