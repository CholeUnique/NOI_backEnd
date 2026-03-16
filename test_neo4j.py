"""
Neo4j 连接诊断脚本
运行方式：在 noi_backend 目录下
  cd noi_backend
  conda activate NoI
  python test_neo4j.py
"""
import os
from dotenv import load_dotenv

# 加载 .env
load_dotenv()

print("=" * 60)
print("1. 检查环境变量")
print("=" * 60)

env_vars = {
    "BEHAVIOR_GRAPH_STORE": os.getenv("BEHAVIOR_GRAPH_STORE"),
    "NEO4J_URI": os.getenv("NEO4J_URI"),
    "NEO4J_USER": os.getenv("NEO4J_USER"),
    "NEO4J_USERNAME": os.getenv("NEO4J_USERNAME"),
    "NEO4J_PASSWORD": os.getenv("NEO4J_PASSWORD"),
    "NEO4J_DATABASE": os.getenv("NEO4J_DATABASE"),
}

for k, v in env_vars.items():
    status = "✓" if v else "✗ (未设置)"
    display_v = v if k != "NEO4J_PASSWORD" else ("*" * len(v) if v else None)
    print(f"  {k}: {display_v} {status}")

print()
print("=" * 60)
print("2. 尝试初始化 Neo4j Driver")
print("=" * 60)

try:
    from app.neo4j import get_neo4j_driver, get_neo4j_database_name
    
    driver = get_neo4j_driver()
    db_name = get_neo4j_database_name()
    
    if driver is None:
        print("  ✗ Driver 初始化返回 None！")
        print("    可能原因：NEO4J_URI/NEO4J_USER(或NEO4J_USERNAME)/NEO4J_PASSWORD 缺失")
    else:
        print(f"  ✓ Driver 初始化成功")
        print(f"  ✓ 数据库名称: {db_name or '(默认)'}")
except Exception as e:
    print(f"  ✗ Driver 初始化异常: {e}")
    driver = None

print()
print("=" * 60)
print("3. 尝试连接并查询")
print("=" * 60)

if driver:
    try:
        session_kwargs = {"database": db_name} if db_name else {}
        with driver.session(**session_kwargs) as session:
            # 简单连接测试
            result = session.run("RETURN 1 AS test")
            record = result.single()
            print(f"  ✓ 连接测试成功: {record['test']}")
            
            # 查询现有节点数量
            result = session.run("MATCH (n) RETURN labels(n) AS labels, count(n) AS cnt")
            records = list(result)
            if records:
                print(f"  ✓ 当前数据库节点统计:")
                for r in records:
                    print(f"      {r['labels']}: {r['cnt']}")
            else:
                print("  ⚠ 数据库中没有任何节点")
            
            # 专门查 BehaviorEvent
            result = session.run("MATCH (e:BehaviorEvent) RETURN count(e) AS cnt")
            cnt = result.single()["cnt"]
            print(f"  → BehaviorEvent 节点数量: {cnt}")
            
            # 专门查 BehaviorObject
            result = session.run("MATCH (o:BehaviorObject) RETURN count(o) AS cnt")
            cnt = result.single()["cnt"]
            print(f"  → BehaviorObject 节点数量: {cnt}")
            
    except Exception as e:
        print(f"  ✗ 查询异常: {e}")
else:
    print("  (跳过：Driver 未初始化)")

print()
print("=" * 60)
print("4. 模拟写入测试（会创建一个测试节点然后删除）")
print("=" * 60)

if driver:
    try:
        session_kwargs = {"database": db_name} if db_name else {}
        with driver.session(**session_kwargs) as session:
            # 写入测试节点
            session.run("""
                CREATE (t:TestNode {id: 'test_neo4j_script', created_at: datetime()})
            """)
            print("  ✓ 写入测试节点成功")
            
            # 读取验证
            result = session.run("MATCH (t:TestNode {id: 'test_neo4j_script'}) RETURN t")
            record = result.single()
            if record:
                print("  ✓ 读取测试节点成功")
            else:
                print("  ✗ 读取测试节点失败")
            
            # 删除测试节点
            session.run("MATCH (t:TestNode {id: 'test_neo4j_script'}) DELETE t")
            print("  ✓ 测试节点已清理")
            
    except Exception as e:
        print(f"  ✗ 写入测试异常: {e}")
else:
    print("  (跳过：Driver 未初始化)")

print()
print("=" * 60)
print("诊断完成")
print("=" * 60)
