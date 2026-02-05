"""
技能系统
包含所有可用的技能实现
"""

from .registry import SkillRegistry, skill_registry, get_skill_registry

from .web_tools import (
    WebSearchSkill,
    WebScraperSkill,
    TrendingTopicsSkill,
    fetch_url_content
)

from .social_tools import (
    SocialPostSkill,
    SocialCommentSkill,
    SocialAnalyticsSkill,
    ContentValidatorSkill,
    SocialPlatform,
    PostStatus,
    format_social_content
)

__all__ = [
    # 注册中心
    "SkillRegistry",
    "skill_registry",
    "get_skill_registry",
    # Web 技能
    "WebSearchSkill",
    "WebScraperSkill",
    "TrendingTopicsSkill",
    "fetch_url_content",
    # 社交媒体技能
    "SocialPostSkill",
    "SocialCommentSkill",
    "SocialAnalyticsSkill",
    "ContentValidatorSkill",
    "SocialPlatform",
    "PostStatus",
    "format_social_content",
]


def register_all_skills():
    """注册所有内置技能"""
    registry = get_skill_registry()
    
    # 注册 Web 技能
    registry.register(WebSearchSkill())
    registry.register(WebScraperSkill())
    registry.register(TrendingTopicsSkill())
    registry.register_function(fetch_url_content)
    
    # 注册社交媒体技能
    registry.register(SocialPostSkill())
    registry.register(SocialCommentSkill())
    registry.register(SocialAnalyticsSkill())
    registry.register(ContentValidatorSkill())
    registry.register_function(format_social_content)
    
    return registry
