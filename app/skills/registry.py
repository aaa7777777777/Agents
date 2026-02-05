"""
技能注册中心
负责技能的注册、发现和管理
"""

import importlib
import inspect
import pkgutil
from typing import Any, Callable, Dict, List, Optional, Type
from pathlib import Path

from app.core.base_skill import (
    BaseSkill,
    SkillCategory,
    SkillDefinition,
    SkillResult
)
from app.core.base_agent import AgentRole


class SkillRegistry:
    """
    技能注册中心
    提供技能的注册、发现、查询和调用功能
    """
    
    _instance: Optional["SkillRegistry"] = None
    
    def __new__(cls, *args, **kwargs):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        
        self._initialized = True
        self._skills: Dict[str, BaseSkill] = {}
        self._skill_functions: Dict[str, Callable] = {}
        self._agent_skills: Dict[AgentRole, List[str]] = {
            role: [] for role in AgentRole
        }
        self._category_skills: Dict[SkillCategory, List[str]] = {
            cat: [] for cat in SkillCategory
        }
    
    def register(
        self,
        skill: BaseSkill,
        agent_roles: Optional[List[AgentRole]] = None
    ) -> None:
        """
        注册技能实例
        
        Args:
            skill: 技能实例
            agent_roles: 可使用该技能的 Agent 角色列表
        """
        name = skill.name
        self._skills[name] = skill
        
        # 注册到分类
        category = skill.definition.category
        if name not in self._category_skills[category]:
            self._category_skills[category].append(name)
        
        # 注册到 Agent 角色
        if agent_roles:
            for role in agent_roles:
                if name not in self._agent_skills[role]:
                    self._agent_skills[role].append(name)
        else:
            # 默认所有角色可用
            for role in AgentRole:
                if name not in self._agent_skills[role]:
                    self._agent_skills[role].append(name)
    
    def register_function(
        self,
        func: Callable,
        agent_roles: Optional[List[AgentRole]] = None
    ) -> None:
        """
        注册技能函数（使用 @skill 装饰器的函数）
        
        Args:
            func: 技能函数
            agent_roles: 可使用该技能的 Agent 角色列表
        """
        if not hasattr(func, "skill_definition"):
            raise ValueError(f"Function {func.__name__} is not a skill function")
        
        definition: SkillDefinition = func.skill_definition
        name = definition.name
        
        self._skill_functions[name] = func
        
        # 注册到分类
        category = definition.category
        if name not in self._category_skills[category]:
            self._category_skills[category].append(name)
        
        # 注册到 Agent 角色
        if agent_roles:
            for role in agent_roles:
                if name not in self._agent_skills[role]:
                    self._agent_skills[role].append(name)
        else:
            for role in AgentRole:
                if name not in self._agent_skills[role]:
                    self._agent_skills[role].append(name)
    
    def unregister(self, name: str) -> bool:
        """
        注销技能
        
        Args:
            name: 技能名称
            
        Returns:
            bool: 是否注销成功
        """
        if name in self._skills:
            skill = self._skills.pop(name)
            category = skill.definition.category
            if name in self._category_skills[category]:
                self._category_skills[category].remove(name)
            for role in AgentRole:
                if name in self._agent_skills[role]:
                    self._agent_skills[role].remove(name)
            return True
        
        if name in self._skill_functions:
            func = self._skill_functions.pop(name)
            definition = func.skill_definition
            category = definition.category
            if name in self._category_skills[category]:
                self._category_skills[category].remove(name)
            for role in AgentRole:
                if name in self._agent_skills[role]:
                    self._agent_skills[role].remove(name)
            return True
        
        return False
    
    def get_skill(self, name: str) -> Optional[BaseSkill]:
        """
        获取技能实例
        
        Args:
            name: 技能名称
            
        Returns:
            Optional[BaseSkill]: 技能实例
        """
        return self._skills.get(name)
    
    def get_skill_function(self, name: str) -> Optional[Callable]:
        """
        获取技能函数
        
        Args:
            name: 技能名称
            
        Returns:
            Optional[Callable]: 技能函数
        """
        return self._skill_functions.get(name)
    
    def get_skill_definition(self, name: str) -> Optional[SkillDefinition]:
        """
        获取技能定义
        
        Args:
            name: 技能名称
            
        Returns:
            Optional[SkillDefinition]: 技能定义
        """
        if name in self._skills:
            return self._skills[name].definition
        if name in self._skill_functions:
            return self._skill_functions[name].skill_definition
        return None
    
    def get_skills_for_agent(self, role: AgentRole) -> List[str]:
        """
        获取指定 Agent 角色可用的技能列表
        
        Args:
            role: Agent 角色
            
        Returns:
            List[str]: 技能名称列表
        """
        return self._agent_skills.get(role, [])
    
    def get_skills_by_category(self, category: SkillCategory) -> List[str]:
        """
        获取指定分类的技能列表
        
        Args:
            category: 技能分类
            
        Returns:
            List[str]: 技能名称列表
        """
        return self._category_skills.get(category, [])
    
    def get_all_skills(self) -> List[str]:
        """获取所有技能名称"""
        return list(self._skills.keys()) + list(self._skill_functions.keys())
    
    def get_tools_schema(
        self,
        skill_names: Optional[List[str]] = None,
        role: Optional[AgentRole] = None
    ) -> List[Dict[str, Any]]:
        """
        获取技能的 OpenAI Tool Schema
        
        Args:
            skill_names: 技能名称列表（可选）
            role: Agent 角色（可选，用于过滤）
            
        Returns:
            List[Dict]: Tool Schema 列表
        """
        if skill_names is None:
            if role:
                skill_names = self.get_skills_for_agent(role)
            else:
                skill_names = self.get_all_skills()
        
        schemas = []
        for name in skill_names:
            definition = self.get_skill_definition(name)
            if definition:
                schemas.append(definition.to_openai_tool())
        
        return schemas
    
    async def execute_skill(
        self,
        name: str,
        **kwargs
    ) -> SkillResult:
        """
        执行技能
        
        Args:
            name: 技能名称
            **kwargs: 技能参数
            
        Returns:
            SkillResult: 执行结果
        """
        # 优先查找技能实例
        if name in self._skills:
            return await self._skills[name].run(**kwargs)
        
        # 查找技能函数
        if name in self._skill_functions:
            return await self._skill_functions[name](**kwargs)
        
        return SkillResult.failure_result(f"Skill not found: {name}")
    
    def auto_discover(self, package_path: Optional[str] = None) -> int:
        """
        自动发现并注册技能
        
        Args:
            package_path: 技能包路径（默认为 app.skills）
            
        Returns:
            int: 发现的技能数量
        """
        if package_path is None:
            package_path = "app.skills"
        
        count = 0
        
        try:
            package = importlib.import_module(package_path)
            package_dir = Path(package.__file__).parent
            
            for _, module_name, _ in pkgutil.iter_modules([str(package_dir)]):
                if module_name.startswith("_"):
                    continue
                
                module = importlib.import_module(f"{package_path}.{module_name}")
                
                # 查找技能类
                for name, obj in inspect.getmembers(module):
                    if (inspect.isclass(obj) and 
                        issubclass(obj, BaseSkill) and 
                        obj is not BaseSkill):
                        try:
                            skill_instance = obj()
                            self.register(skill_instance)
                            count += 1
                        except Exception as e:
                            print(f"Error registering skill {name}: {e}")
                    
                    # 查找技能函数
                    elif callable(obj) and hasattr(obj, "is_skill") and obj.is_skill:
                        try:
                            self.register_function(obj)
                            count += 1
                        except Exception as e:
                            print(f"Error registering skill function {name}: {e}")
        
        except Exception as e:
            print(f"Error auto-discovering skills: {e}")
        
        return count


# 全局技能注册中心实例
skill_registry = SkillRegistry()


def get_skill_registry() -> SkillRegistry:
    """获取技能注册中心单例"""
    return skill_registry
