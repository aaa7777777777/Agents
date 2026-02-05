# Qwen Social Agent Pro

基于 Qwen 1.7B 的多 Agent 社交媒体内容生成系统。采用 LangGraph 风格的编排架构，支持多角色协作、多层记忆和可扩展的技能系统。

## 特性

- **多 Agent 协作**：Supervisor（调度）、Searcher（搜索）、Writer（写作）、Reviewer（审核）四大角色分工明确
- **智能路由**：基于 LangGraph 的 DAG 编排，支持条件路由和循环优化
- **多层记忆**：短期记忆（Redis）、长期记忆（持久化）、语义记忆（ChromaDB）
- **可扩展技能**：插件化的技能系统，支持自定义工具
- **多平台适配**：支持微博、小红书、Twitter 等多平台内容风格
- **内容审核**：L1 硬校验 + L2 软评估的双层审核机制

## 架构

```
qwen-social-agent-pro/
├── app/
│   ├── main.py                 # FastAPI 入口
│   ├── config.py               # 配置管理
│   ├── core/                   # 核心抽象层
│   │   ├── base_agent.py       # Agent 基类
│   │   ├── base_skill.py       # 技能基类
│   │   ├── base_memory.py      # 记忆基类
│   │   └── template_engine.py  # 模板引擎
│   ├── services/               # 服务适配层
│   │   ├── llm_engine.py       # LLM 引擎
│   │   ├── vector_db.py        # 向量数据库
│   │   └── cache.py            # 缓存服务
│   ├── memory/                 # 记忆系统
│   │   ├── short_term.py       # 短期记忆
│   │   ├── long_term.py        # 长期记忆
│   │   ├── semantic.py         # 语义记忆
│   │   └── manager.py          # 统一管理器
│   ├── skills/                 # 技能系统
│   │   ├── registry.py         # 技能注册中心
│   │   ├── web_tools.py        # 网页工具
│   │   └── social_tools.py     # 社交媒体工具
│   ├── agents/                 # Agent 实现
│   │   ├── supervisor_agent.py # 调度员
│   │   ├── searcher_agent.py   # 搜索员
│   │   ├── writer_agent.py     # 写手
│   │   └── reviewer_agent.py   # 审核员
│   ├── orchestration/          # 编排层
│   │   ├── graph_state.py      # 状态定义
│   │   ├── graph_edges.py      # 边路由
│   │   └── workflow.py         # 工作流
│   └── prompts/                # 提示词模板
│       ├── system_niche/       # 领域人设
│       └── sops/               # SOP 模板
├── config/                     # 配置文件
├── scripts/                    # 部署脚本
├── docker-compose.yml          # Docker 编排
├── Dockerfile                  # 容器构建
└── requirements.txt            # Python 依赖
```

## 快速开始

### 环境要求

- Python 3.11+
- Docker & Docker Compose
- 4GB+ 内存
- （可选）NVIDIA GPU

### 本地开发

```bash
# 1. 克隆项目
git clone https://github.com/your-repo/qwen-social-agent-pro.git
cd qwen-social-agent-pro

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 填写配置

# 5. 启动依赖服务
docker compose up -d redis chromadb ollama

# 6. 下载模型
docker exec qwen-ollama ollama pull qwen:1.8b

# 7. 启动应用
python -m app.main
```

### Docker 部署

```bash
# 一键部署（Ubuntu）
sudo bash scripts/deploy.sh

# 或手动部署
docker compose up -d
```

### 访问服务

- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

## API 使用

### 生成内容

```bash
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{
    "content": "写一篇关于 AI 发展趋势的微博",
    "platform": "weibo",
    "niche": "tech",
    "style": "professional"
  }'
```

### 响应示例

```json
{
  "success": true,
  "task_id": "xxx-xxx-xxx",
  "status": "completed",
  "output": "【AI 发展趋势】2024年，AI 正在...",
  "generated_content": {
    "title": "AI 发展趋势",
    "content": "...",
    "tags": ["AI", "人工智能", "科技"]
  },
  "review_result": {
    "passed": true,
    "score": 0.85
  }
}
```

## 配置说明

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `LLM_MODEL` | LLM 模型名称 | `qwen:1.8b` |
| `REVIEW_THRESHOLD` | 审核通过阈值 | `0.7` |
| `MAX_ITERATIONS` | 最大迭代次数 | `10` |
| `REDIS_URL` | Redis 连接地址 | `redis://localhost:6379/0` |

## 扩展开发

### 添加新技能

```python
from app.core.base_skill import BaseSkill, SkillDefinition, SkillResult

class MyCustomSkill(BaseSkill):
    def _build_definition(self) -> SkillDefinition:
        return SkillDefinition(
            name="my_skill",
            description="我的自定义技能",
            parameters=[...]
        )
    
    async def execute(self, **kwargs) -> SkillResult:
        # 实现技能逻辑
        return SkillResult.success_result(data=...)
```

### 添加新 Agent

```python
from app.core.base_agent import BaseAgent, AgentRole

class MyAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="my_agent",
            role=AgentRole.EXECUTOR,
            description="我的自定义 Agent"
        )
    
    async def execute(self, context) -> AgentResult:
        # 实现 Agent 逻辑
        pass
```

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！
