"""
pytest 配置文件
提供测试所需的 fixtures
"""
import pytest
import os
import sys

# 确保项目根目录在路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import FastAPI

# 测试数据库 URL（使用内存 SQLite）
# 注意：pgvector 功能在 SQLite 中不可用，相关测试需要跳过或 mock
TEST_DATABASE_URL = "sqlite:///./test.db"


@pytest.fixture(scope="session")
def engine():
    """创建测试数据库引擎"""
    from app.database import Base
    from app.models.core import User
    
    engine = create_engine(
        TEST_DATABASE_URL, 
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine, tables=[User.__table__])
    yield engine
    Base.metadata.drop_all(bind=engine, tables=[User.__table__])
    engine.dispose()
    
    # 清理测试数据库文件
    if os.path.exists("./test.db"):
        os.remove("./test.db")


@pytest.fixture(scope="function")
def db_session(engine):
    """创建测试数据库会话"""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="function")
def client(db_session):
    """创建测试客户端"""
    from app.database import get_db
    from app.routers import auth
    
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    test_app = FastAPI()
    
    @test_app.get("/")
    async def root():
        return {"message": "NoI System Backend is Running!"}
    
    @test_app.get("/health")
    async def health_check():
        return {"status": "ok", "database": "connected"}
    
    test_app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
    
    test_app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(test_app) as test_client:
        yield test_client
    
    test_app.dependency_overrides.clear()


@pytest.fixture
def test_user_data():
    """测试用户数据"""
    return {
        "username": "testuser",
        "email": "test@example.com",
        "password": "testpassword123"
    }


@pytest.fixture
def auth_headers(client, test_user_data):
    """获取已认证用户的请求头"""
    # 先注册用户
    register_response = client.post("/api/auth/register", json=test_user_data)
    if register_response.status_code not in (200, 201):
        login_response = client.post("/api/auth/login", json={
            "username": test_user_data["username"],
            "password": test_user_data["password"]
        })
        token = login_response.json().get("access_token")
        return {"Authorization": f"Bearer {token}"} if token else {}
    
    login_response = client.post("/api/auth/login", json={
        "username": test_user_data["username"],
        "password": test_user_data["password"]
    })
    token = login_response.json().get("access_token")
    return {"Authorization": f"Bearer {token}"} if token else {}
