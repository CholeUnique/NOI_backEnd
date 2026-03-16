"""
认证服务基础测试
"""
import pytest


def test_health_check(client):
    """测试健康检查接口"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_root_endpoint(client):
    """测试根路径"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data


class TestUserRegistration:
    """用户注册测试"""
    
    def test_register_new_user(self, client, test_user_data):
        """测试注册新用户"""
        response = client.post("/api/auth/register", json=test_user_data)
        # 可能返回 200 或 201，取决于实现
        assert response.status_code in [200, 201]
    
    def test_register_duplicate_user(self, client, test_user_data):
        """测试重复注册"""
        # 第一次注册
        client.post("/api/auth/register", json=test_user_data)
        
        # 第二次注册应该失败
        response = client.post("/api/auth/register", json=test_user_data)
        assert response.status_code in [400, 409]
    
    def test_register_invalid_email(self, client):
        """测试无效邮箱"""
        response = client.post("/api/auth/register", json={
            "username": "testuser2",
            "email": "invalid-email",
            "password": "testpassword123"
        })
        assert response.status_code == 422  # Validation error


class TestUserLogin:
    """用户登录测试"""
    
    def test_login_success(self, client, test_user_data):
        """测试成功登录"""
        # 先注册
        client.post("/api/auth/register", json=test_user_data)
        
        # 再登录
        response = client.post("/api/auth/login", json={
            "username": test_user_data["username"],
            "password": test_user_data["password"]
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
    
    def test_login_wrong_password(self, client, test_user_data):
        """测试错误密码"""
        # 先注册
        client.post("/api/auth/register", json=test_user_data)
        
        # 用错误密码登录
        response = client.post("/api/auth/login", json={
            "username": test_user_data["username"],
            "password": "wrongpassword"
        })
        assert response.status_code in [400, 401]
    
    def test_login_nonexistent_user(self, client):
        """测试不存在的用户"""
        response = client.post("/api/auth/login", json={
            "username": "nonexistent",
            "password": "somepassword"
        })
        assert response.status_code in [400, 401, 404]
