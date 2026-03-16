from sqlalchemy import create_engine, text
import os

# 获取数据库连接字符串 (假设默认值)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/noi_db")

def add_column():
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        try:
            # 尝试添加 mind_map_json 列
            conn.execute(text("ALTER TABLE assets ADD COLUMN IF NOT EXISTS mind_map_json JSONB;"))
            conn.commit()
            print("✅ Successfully added 'mind_map_json' column to 'assets' table.")
        except Exception as e:
            print(f"❌ Failed to add column: {e}")

if __name__ == "__main__":
    add_column()
