"""
FastAPI 应用入口
提供 RESTful API 接口
"""

import uuid
import asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import settings
from app.orchestration import AgentWorkflow, create_default_workflow
from app.skills import register_all_skills
from app.memory import get_memory_manager


# ==================== 请求/响应模型 ====================

class GenerateRequest(BaseModel):
    """内容生成请求"""
    content: str = Field(..., description="用户输入的内容或指令")
    platform: Optional[str] = Field("general", description="目标平台")
    niche: Optional[str] = Field("general", description="垂直领域")
    style: Optional[str] = Field(None, description="写作风格")
    user_id: Optional[str] = Field(None, description="用户 ID")
    thread_id: Optional[str] = Field(None, description="会话线程 ID")
    metadata: Optional[Dict[str, Any]] = Field(None, description="额外元数据")


class GenerateResponse(BaseModel):
    """内容生成响应"""
    success: bool
    task_id: str
    status: str
    output: Optional[str] = None
    generated_content: Optional[Dict[str, Any]] = None
    review_result: Optional[Dict[str, Any]] = None
    errors: List[str] = []
    metadata: Dict[str, Any] = {}


class TaskStatusResponse(BaseModel):
    """任务状态响应"""
    task_id: str
    status: str
    progress: float
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    version: str
    timestamp: str
    services: Dict[str, str]


# ==================== 全局状态 ====================

# 任务存储（生产环境应使用 Redis）
task_store: Dict[str, Dict[str, Any]] = {}

# 工作流实例
workflow: Optional[AgentWorkflow] = None


# ==================== 生命周期管理 ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global workflow
    
    # 启动时初始化
    print("🚀 Starting Qwen Social Agent Pro...")
    
    # 注册所有技能
    register_all_skills()
    print("✅ Skills registered")
    
    # 创建工作流
    workflow = create_default_workflow()
    print("✅ Workflow initialized")
    
    # 设置回调（可选）
    workflow.set_callbacks(
        on_agent_start=lambda agent, state: print(f"▶️ Agent started: {agent}"),
        on_agent_end=lambda agent, result, state: print(
            f"✅ Agent finished: {agent}, success: {result.success}"
        )
    )
    
    print("🎉 Application ready!")
    
    yield
    
    # 关闭时清理
    print("👋 Shutting down...")


# ==================== 创建应用 ====================

app = FastAPI(
    title="Qwen Social Agent Pro",
    description="基于 Qwen 1.7B 的多 Agent 社交媒体内容生成系统",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== API 路由 ====================

@app.get("/", response_model=HealthResponse)
async def root():
    """根路径 - 健康检查"""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.now().isoformat(),
        services={
            "api": "running",
            "workflow": "ready" if workflow else "not initialized"
        }
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查端点"""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.now().isoformat(),
        services={
            "api": "running",
            "workflow": "ready" if workflow else "not initialized",
            "memory": "connected",
            "llm": "available"
        }
    )


@app.post("/api/v1/generate", response_model=GenerateResponse)
async def generate_content(
    request: GenerateRequest,
    background_tasks: BackgroundTasks
):
    """
    生成社交媒体内容
    
    这是主要的内容生成接口，会启动完整的多 Agent 工作流。
    """
    if not workflow:
        raise HTTPException(status_code=503, detail="Workflow not initialized")
    
    # 生成任务 ID
    task_id = str(uuid.uuid4())
    thread_id = request.thread_id or task_id
    
    # 初始化任务状态
    task_store[task_id] = {
        "status": "pending",
        "progress": 0.0,
        "created_at": datetime.now().isoformat()
    }
    
    # 构建元数据
    metadata = request.metadata or {}
    metadata.update({
        "platform": request.platform,
        "niche": request.niche,
        "style": request.style
    })
    
    try:
        # 同步执行工作流（也可以改为异步）
        task_store[task_id]["status"] = "running"
        task_store[task_id]["progress"] = 0.1
        
        result = await workflow.run(
            user_input=request.content,
            thread_id=thread_id,
            user_id=request.user_id,
            metadata=metadata
        )
        
        # 更新任务状态
        task_store[task_id]["status"] = "completed" if result["success"] else "failed"
        task_store[task_id]["progress"] = 1.0
        task_store[task_id]["result"] = result
        
        return GenerateResponse(
            success=result["success"],
            task_id=task_id,
            status=result["status"],
            output=result.get("output"),
            generated_content=result.get("generated_content"),
            review_result=result.get("review_result"),
            errors=result.get("errors", []),
            metadata=result.get("metadata", {})
        )
        
    except Exception as e:
        task_store[task_id]["status"] = "failed"
        task_store[task_id]["error"] = str(e)
        
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/generate/async", response_model=Dict[str, str])
async def generate_content_async(
    request: GenerateRequest,
    background_tasks: BackgroundTasks
):
    """
    异步生成内容
    
    返回任务 ID，可通过 /api/v1/tasks/{task_id} 查询状态
    """
    if not workflow:
        raise HTTPException(status_code=503, detail="Workflow not initialized")
    
    task_id = str(uuid.uuid4())
    thread_id = request.thread_id or task_id
    
    # 初始化任务
    task_store[task_id] = {
        "status": "pending",
        "progress": 0.0,
        "created_at": datetime.now().isoformat()
    }
    
    # 后台执行
    async def run_workflow():
        try:
            task_store[task_id]["status"] = "running"
            
            metadata = request.metadata or {}
            metadata.update({
                "platform": request.platform,
                "niche": request.niche,
                "style": request.style
            })
            
            result = await workflow.run(
                user_input=request.content,
                thread_id=thread_id,
                user_id=request.user_id,
                metadata=metadata
            )
            
            task_store[task_id]["status"] = "completed" if result["success"] else "failed"
            task_store[task_id]["progress"] = 1.0
            task_store[task_id]["result"] = result
            
        except Exception as e:
            task_store[task_id]["status"] = "failed"
            task_store[task_id]["error"] = str(e)
    
    background_tasks.add_task(run_workflow)
    
    return {"task_id": task_id, "message": "Task created"}


@app.get("/api/v1/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """获取任务状态"""
    if task_id not in task_store:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = task_store[task_id]
    
    return TaskStatusResponse(
        task_id=task_id,
        status=task["status"],
        progress=task.get("progress", 0.0),
        result=task.get("result"),
        error=task.get("error")
    )


@app.delete("/api/v1/tasks/{task_id}")
async def cancel_task(task_id: str):
    """取消任务"""
    if task_id not in task_store:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = task_store[task_id]
    
    if task["status"] in ["completed", "failed"]:
        return {"message": "Task already finished"}
    
    task["status"] = "cancelled"
    
    return {"message": "Task cancelled"}


# ==================== 记忆管理 API ====================

@app.post("/api/v1/memory/store")
async def store_memory(
    content: str,
    user_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    memory_type: str = "short_term"
):
    """存储记忆"""
    from app.core.base_memory import MemoryType
    
    manager = get_memory_manager()
    
    type_map = {
        "short_term": MemoryType.SHORT_TERM,
        "long_term": MemoryType.LONG_TERM,
        "semantic": MemoryType.SEMANTIC
    }
    
    success = await manager.store(
        content=content,
        memory_type=type_map.get(memory_type, MemoryType.SHORT_TERM),
        user_id=user_id,
        thread_id=thread_id
    )
    
    return {"success": success}


@app.get("/api/v1/memory/search")
async def search_memory(
    query: str,
    user_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    limit: int = 10
):
    """搜索记忆"""
    manager = get_memory_manager()
    
    result = await manager.search(
        query_text=query,
        user_id=user_id,
        thread_id=thread_id,
        limit=limit
    )
    
    return {
        "total_count": result.total_count,
        "query_time": result.query_time,
        "entries": [
            {
                "content": e.content,
                "type": e.memory_type.value,
                "importance": e.importance
            }
            for e in result.get_all_entries()
        ]
    }


# ==================== 技能管理 API ====================

@app.get("/api/v1/skills")
async def list_skills():
    """列出所有可用技能"""
    from app.skills import get_skill_registry
    
    registry = get_skill_registry()
    skills = []
    
    for name in registry.get_all_skills():
        definition = registry.get_skill_definition(name)
        if definition:
            skills.append({
                "name": definition.name,
                "description": definition.description,
                "category": definition.category.value,
                "parameters": [
                    {
                        "name": p.name,
                        "type": p.type,
                        "description": p.description,
                        "required": p.required
                    }
                    for p in definition.parameters
                ]
            })
    
    return {"skills": skills, "count": len(skills)}


@app.post("/api/v1/skills/{skill_name}/execute")
async def execute_skill(skill_name: str, parameters: Dict[str, Any]):
    """执行指定技能"""
    from app.skills import get_skill_registry
    
    registry = get_skill_registry()
    
    if skill_name not in registry.get_all_skills():
        raise HTTPException(status_code=404, detail=f"Skill not found: {skill_name}")
    
    result = await registry.execute_skill(skill_name, **parameters)
    
    return {
        "success": result.success,
        "data": result.data,
        "error": result.error,
        "metadata": result.metadata
    }


# ==================== 启动入口 ====================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
