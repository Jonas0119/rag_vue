"""
数据库连接管理器
"""
import sqlite3
import os
from pathlib import Path
from typing import Optional
from contextlib import contextmanager


class DatabaseManager:
    """SQLite 数据库管理器"""
    
    def __init__(self, db_path: str = "data/database/rag_system.db"):
        self.db_path = db_path
        self._ensure_db_directory()
        self._init_database()
    
    def _ensure_db_directory(self):
        """确保数据库目录存在"""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
    
    def _init_database(self):
        """初始化数据库（创建表）"""
        sql_file = Path(__file__).parent / "init_db.sql"
        
        if not sql_file.exists():
            raise FileNotFoundError(f"数据库初始化脚本不存在: {sql_file}")
        
        # 读取 SQL 脚本
        with open(sql_file, 'r', encoding='utf-8') as f:
            sql_script = f.read()
        
        # 执行初始化
        conn = self.get_connection()
        try:
            conn.executescript(sql_script)
            conn.commit()
        finally:
            conn.close()
    
    def get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row  # 返回字典式行
        return conn
    
    @contextmanager
    def get_cursor(self):
        """上下文管理器：获取游标并自动提交/关闭"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()
    
    def execute_query(self, query: str, params: tuple = ()):
        """执行查询（SELECT）"""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()
    
    def execute_one(self, query: str, params: tuple = ()):
        """执行查询并返回一条结果"""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()
    
    def execute_update(self, query: str, params: tuple = ()):
        """执行更新（INSERT/UPDATE/DELETE）"""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.rowcount
    
    def execute_insert(self, query: str, params: tuple = ()):
        """执行插入并返回插入的 ID"""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.lastrowid


# 全局数据库管理器实例
_db_manager: Optional[DatabaseManager] = None


def get_db_manager(db_path: str = "data/database/rag_system.db") -> DatabaseManager:
    """获取全局数据库管理器实例（单例模式）"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager(db_path)
    return _db_manager


def init_database(db_path: str = "data/database/rag_system.db"):
    """初始化数据库（用于手动调用）"""
    db_manager = DatabaseManager(db_path)
    print(f"✅ 数据库已初始化: {db_path}")
    return db_manager


if __name__ == "__main__":
    # 测试数据库连接
    print("测试数据库连接...")
    db = init_database()
    
    # 查询用户表
    users = db.execute_query("SELECT * FROM users LIMIT 5")
    print(f"用户表记录数: {len(users)}")
    
    print("✅ 数据库测试成功！")

