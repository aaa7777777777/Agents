"""
网页工具技能
提供网页抓取、热点搜索等功能
"""

import asyncio
import httpx
from typing import Any, Dict, List, Optional
from datetime import datetime

from app.core.base_skill import (
    BaseSkill,
    SkillCategory,
    SkillParameter,
    SkillDefinition,
    SkillResult,
    skill
)
from app.config import settings


class WebSearchSkill(BaseSkill):
    """网页搜索技能"""
    
    def __init__(self):
        super().__init__()
        self.client = httpx.AsyncClient(timeout=30)
    
    def _build_definition(self) -> SkillDefinition:
        return SkillDefinition(
            name="web_search",
            description="搜索网页内容，获取相关信息",
            category=SkillCategory.WEB,
            parameters=[
                SkillParameter(
                    name="query",
                    type="string",
                    description="搜索关键词",
                    required=True
                ),
                SkillParameter(
                    name="num_results",
                    type="integer",
                    description="返回结果数量",
                    required=False,
                    default=5
                ),
                SkillParameter(
                    name="language",
                    type="string",
                    description="搜索语言",
                    required=False,
                    default="zh-CN"
                )
            ],
            returns="List[Dict] - 搜索结果列表",
            examples=[
                "搜索 '人工智能最新进展'",
                "搜索 'Python 编程教程'"
            ]
        )
    
    async def execute(self, **kwargs) -> SkillResult:
        """执行网页搜索"""
        query = kwargs.get("query", "")
        num_results = kwargs.get("num_results", 5)
        language = kwargs.get("language", "zh-CN")
        
        if not query:
            return SkillResult.failure_result("搜索关键词不能为空")
        
        try:
            # 使用 Serper API（如果配置了）
            if settings.SERPER_API_KEY:
                results = await self._search_with_serper(query, num_results)
            # 使用 Tavily API（如果配置了）
            elif settings.TAVILY_API_KEY:
                results = await self._search_with_tavily(query, num_results)
            else:
                # 模拟搜索结果（用于测试）
                results = self._mock_search_results(query, num_results)
            
            return SkillResult.success_result(
                data=results,
                metadata={"query": query, "count": len(results)}
            )
        except Exception as e:
            return SkillResult.failure_result(f"搜索失败: {str(e)}")
    
    async def _search_with_serper(
        self,
        query: str,
        num_results: int
    ) -> List[Dict[str, Any]]:
        """使用 Serper API 搜索"""
        response = await self.client.post(
            "https://google.serper.dev/search",
            headers={
                "X-API-KEY": settings.SERPER_API_KEY,
                "Content-Type": "application/json"
            },
            json={
                "q": query,
                "num": num_results,
                "gl": "cn",
                "hl": "zh-cn"
            }
        )
        response.raise_for_status()
        data = response.json()
        
        results = []
        for item in data.get("organic", [])[:num_results]:
            results.append({
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
                "source": "serper"
            })
        
        return results
    
    async def _search_with_tavily(
        self,
        query: str,
        num_results: int
    ) -> List[Dict[str, Any]]:
        """使用 Tavily API 搜索"""
        response = await self.client.post(
            "https://api.tavily.com/search",
            headers={
                "Content-Type": "application/json"
            },
            json={
                "api_key": settings.TAVILY_API_KEY,
                "query": query,
                "max_results": num_results,
                "search_depth": "basic"
            }
        )
        response.raise_for_status()
        data = response.json()
        
        results = []
        for item in data.get("results", [])[:num_results]:
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("content", ""),
                "source": "tavily"
            })
        
        return results
    
    def _mock_search_results(
        self,
        query: str,
        num_results: int
    ) -> List[Dict[str, Any]]:
        """模拟搜索结果（用于测试）"""
        return [
            {
                "title": f"关于 {query} 的搜索结果 {i+1}",
                "url": f"https://example.com/result/{i+1}",
                "snippet": f"这是关于 {query} 的第 {i+1} 条搜索结果摘要...",
                "source": "mock"
            }
            for i in range(num_results)
        ]


class WebScraperSkill(BaseSkill):
    """网页抓取技能"""
    
    def __init__(self):
        super().__init__()
        self.client = httpx.AsyncClient(
            timeout=30,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )
    
    def _build_definition(self) -> SkillDefinition:
        return SkillDefinition(
            name="web_scrape",
            description="抓取指定网页的内容",
            category=SkillCategory.WEB,
            parameters=[
                SkillParameter(
                    name="url",
                    type="string",
                    description="要抓取的网页 URL",
                    required=True
                ),
                SkillParameter(
                    name="extract_type",
                    type="string",
                    description="提取类型：text（纯文本）、html（HTML）、markdown（Markdown）",
                    required=False,
                    default="text",
                    enum=["text", "html", "markdown"]
                ),
                SkillParameter(
                    name="max_length",
                    type="integer",
                    description="最大内容长度",
                    required=False,
                    default=5000
                )
            ],
            returns="Dict - 抓取结果"
        )
    
    async def execute(self, **kwargs) -> SkillResult:
        """执行网页抓取"""
        url = kwargs.get("url", "")
        extract_type = kwargs.get("extract_type", "text")
        max_length = kwargs.get("max_length", 5000)
        
        if not url:
            return SkillResult.failure_result("URL 不能为空")
        
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            
            html_content = response.text
            
            if extract_type == "html":
                content = html_content[:max_length]
            elif extract_type == "markdown":
                content = self._html_to_markdown(html_content)[:max_length]
            else:
                content = self._extract_text(html_content)[:max_length]
            
            return SkillResult.success_result(
                data={
                    "url": url,
                    "content": content,
                    "content_type": response.headers.get("content-type", ""),
                    "length": len(content)
                }
            )
        except httpx.HTTPStatusError as e:
            return SkillResult.failure_result(f"HTTP 错误: {e.response.status_code}")
        except Exception as e:
            return SkillResult.failure_result(f"抓取失败: {str(e)}")
    
    def _extract_text(self, html: str) -> str:
        """从 HTML 提取纯文本"""
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(html, "html.parser")
        
        # 移除脚本和样式
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()
        
        # 获取文本
        text = soup.get_text(separator="\n", strip=True)
        
        # 清理多余空行
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines)
    
    def _html_to_markdown(self, html: str) -> str:
        """将 HTML 转换为 Markdown"""
        try:
            import html2text
            converter = html2text.HTML2Text()
            converter.ignore_links = False
            converter.ignore_images = True
            return converter.handle(html)
        except ImportError:
            # 如果没有 html2text，使用简单的文本提取
            return self._extract_text(html)


class TrendingTopicsSkill(BaseSkill):
    """热点话题获取技能"""
    
    def __init__(self):
        super().__init__()
        self.client = httpx.AsyncClient(timeout=30)
    
    def _build_definition(self) -> SkillDefinition:
        return SkillDefinition(
            name="get_trending",
            description="获取当前热点话题和趋势",
            category=SkillCategory.WEB,
            parameters=[
                SkillParameter(
                    name="platform",
                    type="string",
                    description="平台：weibo（微博）、zhihu（知乎）、baidu（百度）、general（综合）",
                    required=False,
                    default="general",
                    enum=["weibo", "zhihu", "baidu", "general"]
                ),
                SkillParameter(
                    name="category",
                    type="string",
                    description="分类：all（全部）、tech（科技）、entertainment（娱乐）、finance（财经）",
                    required=False,
                    default="all"
                ),
                SkillParameter(
                    name="limit",
                    type="integer",
                    description="返回数量",
                    required=False,
                    default=10
                )
            ],
            returns="List[Dict] - 热点话题列表"
        )
    
    async def execute(self, **kwargs) -> SkillResult:
        """获取热点话题"""
        platform = kwargs.get("platform", "general")
        category = kwargs.get("category", "all")
        limit = kwargs.get("limit", 10)
        
        try:
            if platform == "weibo":
                topics = await self._get_weibo_trending(limit)
            elif platform == "zhihu":
                topics = await self._get_zhihu_trending(limit)
            elif platform == "baidu":
                topics = await self._get_baidu_trending(limit)
            else:
                topics = await self._get_general_trending(limit)
            
            # 按分类过滤
            if category != "all":
                topics = [t for t in topics if t.get("category") == category]
            
            return SkillResult.success_result(
                data=topics[:limit],
                metadata={"platform": platform, "category": category}
            )
        except Exception as e:
            return SkillResult.failure_result(f"获取热点失败: {str(e)}")
    
    async def _get_weibo_trending(self, limit: int) -> List[Dict[str, Any]]:
        """获取微博热搜"""
        # 实际项目中应该调用微博 API
        # 这里返回模拟数据
        return [
            {
                "rank": i + 1,
                "title": f"微博热搜话题 {i + 1}",
                "hot_value": 1000000 - i * 50000,
                "url": f"https://s.weibo.com/weibo?q=%23热搜{i+1}%23",
                "platform": "weibo",
                "category": "general",
                "timestamp": datetime.now().isoformat()
            }
            for i in range(limit)
        ]
    
    async def _get_zhihu_trending(self, limit: int) -> List[Dict[str, Any]]:
        """获取知乎热榜"""
        return [
            {
                "rank": i + 1,
                "title": f"知乎热门问题 {i + 1}",
                "hot_value": 500000 - i * 25000,
                "url": f"https://www.zhihu.com/question/{i+1}",
                "platform": "zhihu",
                "category": "general",
                "timestamp": datetime.now().isoformat()
            }
            for i in range(limit)
        ]
    
    async def _get_baidu_trending(self, limit: int) -> List[Dict[str, Any]]:
        """获取百度热搜"""
        return [
            {
                "rank": i + 1,
                "title": f"百度热搜词 {i + 1}",
                "hot_value": 800000 - i * 40000,
                "url": f"https://www.baidu.com/s?wd=热搜{i+1}",
                "platform": "baidu",
                "category": "general",
                "timestamp": datetime.now().isoformat()
            }
            for i in range(limit)
        ]
    
    async def _get_general_trending(self, limit: int) -> List[Dict[str, Any]]:
        """获取综合热点"""
        # 合并多个平台的热点
        all_topics = []
        
        weibo = await self._get_weibo_trending(limit // 3)
        zhihu = await self._get_zhihu_trending(limit // 3)
        baidu = await self._get_baidu_trending(limit // 3)
        
        all_topics.extend(weibo)
        all_topics.extend(zhihu)
        all_topics.extend(baidu)
        
        # 按热度排序
        all_topics.sort(key=lambda x: x.get("hot_value", 0), reverse=True)
        
        return all_topics[:limit]


# 使用装饰器定义的技能函数
@skill(
    name="fetch_url_content",
    description="快速获取 URL 的文本内容",
    category=SkillCategory.WEB,
    parameters=[
        SkillParameter(
            name="url",
            type="string",
            description="要获取的 URL",
            required=True
        )
    ]
)
async def fetch_url_content(url: str) -> SkillResult:
    """快速获取 URL 内容"""
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, "html.parser")
            
            # 移除不需要的元素
            for element in soup(["script", "style"]):
                element.decompose()
            
            text = soup.get_text(separator="\n", strip=True)
            
            return SkillResult.success_result({
                "url": url,
                "content": text[:3000],
                "title": soup.title.string if soup.title else ""
            })
        except Exception as e:
            return SkillResult.failure_result(str(e))
