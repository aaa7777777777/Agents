"""
Skill 抽象基类
定义所有技能的通用接口和基础行为
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import inspect
import functools


class SkillCategory(str, Enum):
    """技能分类枚举"""
    WEB = "web"  # 网页相关
    SOCIAL = "social"  # 社交媒体相关
    DATA = "data"  # 数据处理相关
    UTILITY = "utility"  # 通用工具
    CUSTOM = "custom"  # 自定义


@dataclass
class SkillParameter:
    """技能参数定义"""
    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None
    enum: Optional[List[Any]] = None


@dataclass
class SkillDefinition:
    """技能定义结构"""
    name: str
    description: str
    category: SkillCategory
    parameters: List[SkillParameter] = field(default_factory=list)
    returns: str = "Any"
    examples: List[str] = field(default_factory=list)
    requires_auth: bool = False
    rate_limit: Optional[int] = None  # 每分钟调用次数限制
    
    def to_openai_tool(self) -> Dict[str, Any]:
        """转换为 OpenAI Tool 格式"""
        properties = {}
        required = []
        
        for param in self.parameters:
            prop = {
                "type": param.type,
                "description": param.description
            }
            if param.enum:
                prop["enum"] = param.enum
            properties[param.name] = prop
            
            if param.required:
                required.append(param.name)
        
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }


@dataclass
class SkillResult:
    """技能执行结果"""
    success: bool
    data: Any
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def success_result(cls, data: Any, **kwargs) -> "SkillResult":
        """创建成功结果"""
        return cls(success=True, data=data, **kwargs)
    
    @classmethod
    def failure_result(cls, error: str, **kwargs) -> "SkillResult":
        """创建失败结果"""
        return cls(success=False, data=None, error=error, **kwargs)


class BaseSkill(ABC):
    """
    Skill 抽象基类
    所有具体技能都必须继承此类并实现抽象方法
    """
    
    def __init__(self):
        self._definition: Optional[SkillDefinition] = None
    
    @property
    def definition(self) -> SkillDefinition:
        """获取技能定义"""
        if self._definition is None:
            self._definition = self._build_definition()
        return self._definition
    
    @property
    def name(self) -> str:
        """获取技能名称"""
        return self.definition.name
    
    @property
    def description(self) -> str:
        """获取技能描述"""
        return self.definition.description
    
    @abstractmethod
    def _build_definition(self) -> SkillDefinition:
        """
        构建技能定义
        子类必须实现此方法来定义技能的元信息
        """
        pass
    
    @abstractmethod
    async def execute(self, **kwargs) -> SkillResult:
        """
        执行技能
        子类必须实现此方法
        
        Args:
            **kwargs: 技能参数
            
        Returns:
            SkillResult: 执行结果
        """
        pass
    
    async def validate_params(self, **kwargs) -> Optional[str]:
        """
        验证参数
        返回 None 表示验证通过，否则返回错误信息
        """
        for param in self.definition.parameters:
            if param.required and param.name not in kwargs:
                return f"Missing required parameter: {param.name}"
            
            if param.name in kwargs and param.enum:
                if kwargs[param.name] not in param.enum:
                    return f"Invalid value for {param.name}: must be one of {param.enum}"
        
        return None
    
    async def run(self, **kwargs) -> SkillResult:
        """
        运行技能的完整流程
        包含参数验证和执行
        """
        # 验证参数
        error = await self.validate_params(**kwargs)
        if error:
            return SkillResult.failure_result(error)
        
        try:
            return await self.execute(**kwargs)
        except Exception as e:
            return SkillResult.failure_result(str(e))
    
    def to_tool_schema(self) -> Dict[str, Any]:
        """转换为工具 Schema"""
        return self.definition.to_openai_tool()
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name={self.name})>"


def skill(
    name: str,
    description: str,
    category: SkillCategory = SkillCategory.UTILITY,
    parameters: Optional[List[SkillParameter]] = None,
    requires_auth: bool = False,
    rate_limit: Optional[int] = None
):
    """
    技能装饰器
    用于将普通函数快速转换为技能
    
    Usage:
        @skill(
            name="search_web",
            description="搜索网页内容",
            category=SkillCategory.WEB,
            parameters=[
                SkillParameter(name="query", type="string", description="搜索关键词")
            ]
        )
        async def search_web(query: str) -> SkillResult:
            ...
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(**kwargs) -> SkillResult:
            try:
                result = await func(**kwargs)
                if isinstance(result, SkillResult):
                    return result
                return SkillResult.success_result(result)
            except Exception as e:
                return SkillResult.failure_result(str(e))
        
        # 附加技能定义到函数
        wrapper.skill_definition = SkillDefinition(
            name=name,
            description=description,
            category=category,
            parameters=parameters or [],
            requires_auth=requires_auth,
            rate_limit=rate_limit
        )
        wrapper.is_skill = True
        
        return wrapper
    
    return decorator
