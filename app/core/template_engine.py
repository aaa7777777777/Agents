"""
Prompt 模板引擎
基于 Jinja2 实现灵活的提示词模板渲染
"""

import os
from typing import Any, Dict, Optional
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape, Template


class TemplateEngine:
    """
    Prompt 模板引擎
    支持从文件或字符串渲染模板
    """
    
    _instance: Optional["TemplateEngine"] = None
    
    def __new__(cls, *args, **kwargs):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, templates_dir: Optional[str] = None):
        if hasattr(self, "_initialized"):
            return
        
        self._initialized = True
        
        # 默认模板目录
        if templates_dir is None:
            templates_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "prompts"
            )
        
        self.templates_dir = Path(templates_dir)
        
        # 初始化 Jinja2 环境
        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # 注册自定义过滤器
        self._register_filters()
        
        # 注册全局变量
        self._register_globals()
    
    def _register_filters(self) -> None:
        """注册自定义 Jinja2 过滤器"""
        
        def truncate_text(text: str, length: int = 100, suffix: str = "...") -> str:
            """截断文本"""
            if len(text) <= length:
                return text
            return text[:length - len(suffix)] + suffix
        
        def format_list(items: list, separator: str = "\n- ") -> str:
            """格式化列表"""
            if not items:
                return ""
            return separator + separator.join(str(item) for item in items)
        
        def json_dumps(obj: Any) -> str:
            """JSON 序列化"""
            import json
            return json.dumps(obj, ensure_ascii=False, indent=2)
        
        def word_count(text: str) -> int:
            """统计字数"""
            return len(text)
        
        self.env.filters["truncate_text"] = truncate_text
        self.env.filters["format_list"] = format_list
        self.env.filters["json_dumps"] = json_dumps
        self.env.filters["word_count"] = word_count
    
    def _register_globals(self) -> None:
        """注册全局变量和函数"""
        from datetime import datetime
        
        self.env.globals["now"] = datetime.now
        self.env.globals["today"] = lambda: datetime.now().strftime("%Y-%m-%d")
    
    def render(self, template_name: str, **context) -> str:
        """
        渲染模板文件
        
        Args:
            template_name: 模板文件名（相对于 templates_dir）
            **context: 模板上下文变量
            
        Returns:
            str: 渲染后的字符串
        """
        template = self.env.get_template(template_name)
        return template.render(**context)
    
    def render_string(self, template_string: str, **context) -> str:
        """
        渲染模板字符串
        
        Args:
            template_string: 模板字符串
            **context: 模板上下文变量
            
        Returns:
            str: 渲染后的字符串
        """
        template = self.env.from_string(template_string)
        return template.render(**context)
    
    def get_template(self, template_name: str) -> Template:
        """
        获取模板对象
        
        Args:
            template_name: 模板文件名
            
        Returns:
            Template: Jinja2 模板对象
        """
        return self.env.get_template(template_name)
    
    def list_templates(self, subdir: Optional[str] = None) -> list:
        """
        列出所有模板文件
        
        Args:
            subdir: 子目录（可选）
            
        Returns:
            list: 模板文件名列表
        """
        search_dir = self.templates_dir
        if subdir:
            search_dir = search_dir / subdir
        
        templates = []
        for path in search_dir.rglob("*.j2"):
            rel_path = path.relative_to(self.templates_dir)
            templates.append(str(rel_path))
        
        for path in search_dir.rglob("*.txt"):
            rel_path = path.relative_to(self.templates_dir)
            templates.append(str(rel_path))
        
        return sorted(templates)


class PromptBuilder:
    """
    Prompt 构建器
    提供链式调用来构建复杂的提示词
    """
    
    def __init__(self):
        self._sections: Dict[str, str] = {}
        self._order: list = []
    
    def add_section(self, name: str, content: str) -> "PromptBuilder":
        """添加一个部分"""
        if name not in self._order:
            self._order.append(name)
        self._sections[name] = content
        return self
    
    def add_system(self, content: str) -> "PromptBuilder":
        """添加系统部分"""
        return self.add_section("system", content)
    
    def add_context(self, content: str) -> "PromptBuilder":
        """添加上下文部分"""
        return self.add_section("context", content)
    
    def add_examples(self, examples: list) -> "PromptBuilder":
        """添加示例部分"""
        if examples:
            content = "\n\n".join(f"示例 {i+1}:\n{ex}" for i, ex in enumerate(examples))
            return self.add_section("examples", f"## 示例\n{content}")
        return self
    
    def add_constraints(self, constraints: list) -> "PromptBuilder":
        """添加约束条件"""
        if constraints:
            content = "\n".join(f"- {c}" for c in constraints)
            return self.add_section("constraints", f"## 约束条件\n{content}")
        return self
    
    def add_task(self, task: str) -> "PromptBuilder":
        """添加任务描述"""
        return self.add_section("task", f"## 当前任务\n{task}")
    
    def add_output_format(self, format_desc: str) -> "PromptBuilder":
        """添加输出格式说明"""
        return self.add_section("output_format", f"## 输出格式\n{format_desc}")
    
    def build(self, separator: str = "\n\n") -> str:
        """构建最终的提示词"""
        parts = [self._sections[name] for name in self._order if name in self._sections]
        return separator.join(parts)
    
    def clear(self) -> "PromptBuilder":
        """清空所有部分"""
        self._sections.clear()
        self._order.clear()
        return self


# 全局模板引擎实例
template_engine = TemplateEngine()
