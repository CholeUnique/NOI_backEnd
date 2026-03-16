import os

from dotenv import load_dotenv
from fastapi import FastAPI
from app.database import engine, Base
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.logging import setup_logging
# 必须导入 models，否则 SQLAlchemy 不知道有哪些表需要创建
from app import models 
from app.api.api import api_router

# 导入新的模型包（确保表被创建）
from app.models import event_stream, behavior_graph, memory as memory_models

# 加载环境变量（支持本地与服务器使用 noi_backend/.env）
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_BASE_DIR, ".env"))
setup_logging()

# 1. 自动建表核心代码
# 检查数据库，如果没有对应的表，自动创建
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用程序生命周期管理"""
    # 启动时创建数据库表
    Base.metadata.create_all(bind=engine)
    yield
    # 关闭时清理资源
    pass

# 创建 FastAPI 应用实例
app = FastAPI(
    title="NoI Knowledge Agent",
    version="1.0.0",
    lifespan=lifespan
)
origins = [
    "http://localhost:5173",    # Vue 默认端口
    "http://127.0.0.1:5173",
    "http://localhost:5174", 
    "http://localhost:5175",
    "http://localhost:5176",   # Vue 备用端口
    "http://127.0.0.1:5174",
    "http://127.0.0.1:5176",
    "http://127.0.0.1:5175",
    "http://172.19.192.1:5174",
]

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(api_router)


@app.get("/")
async def root():
    """根路径"""
    return {"message": "NoI System Backend is Running!"}

# 可以在这里测试一下数据库连接
@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "database": "connected"}

from app.services.embedding import embedding_service

@app.get("/test/embedding")
async def test_embedding(text: str = "测试文本"):
    vector = await embedding_service.get_embedding(text)
    return {
        "text": text,
        "vector_length": len(vector),
        "vector_preview": vector[:5] # 只看前5个数字
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
