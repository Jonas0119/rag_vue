"""
数据库连接管理器 - 支持 SQLite 和 PostgreSQL
"""
import sqlite3
import os
from pathlib import Path
from typing import Optional, Union
from contextlib import contextmanager

from utils.config import config
from utils.performance_monitor import monitor_database

# PostgreSQL 相关导入（可选）
try:
    import psycopg2
    from psycopg2 import pool
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    pool = None


class DatabaseManager:
    """数据库管理器 - 支持 SQLite 和 PostgreSQL"""
    
    def __init__(self, db_path: str = "data/database/rag_system.db"):
        self.db_path = db_path
        self.db_type = "postgresql" if config.DATABASE_MODE == "cloud" else "sqlite"
        self._postgres_initialized = False  # PostgreSQL 延迟初始化标志
        self._connection_pool = None  # PostgreSQL 连接池
        
        if self.db_type == "sqlite":
            self._ensure_db_directory()
            self._init_database()
        else:
            # PostgreSQL 模式：只检查配置，不立即连接
            if not config.DATABASE_URL:
                raise ValueError("DATABASE_MODE=cloud 时，必须配置 DATABASE_URL")
            if not PSYCOPG2_AVAILABLE:
                raise ImportError("使用 PostgreSQL 需要安装 psycopg2-binary: pip install psycopg2-binary")
            # 延迟初始化连接池：不在 __init__ 中创建，而是在第一次使用时创建
    
    def _ensure_db_directory(self):
        """确保数据库目录存在（仅 SQLite）"""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
    
    def _init_database(self):
        """初始化 SQLite 数据库（创建表）"""
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
    
    def _init_connection_pool(self):
        """初始化 PostgreSQL 连接池"""
        if self._connection_pool is not None:
            return  # 连接池已创建
        
        try:
            # 创建连接池
            # minconn: 最小连接数（保持活跃连接）
            # maxconn: 最大连接数（峰值并发）
            self._connection_pool = pool.SimpleConnectionPool(
                minconn=2,
                maxconn=10,
                dsn=config.DATABASE_URL
            )
            
            if self._connection_pool is None:
                raise ConnectionError("无法创建 PostgreSQL 连接池")
        except Exception as e:
            raise ConnectionError(f"创建 PostgreSQL 连接池失败: {str(e)}")
    
    def _is_connection_alive(self, conn) -> bool:
        """检查 PostgreSQL 连接是否有效"""
        if conn is None or conn.closed:
            return False
        
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            return True
        except:
            return False
    
    def _init_postgres_database(self):
        """初始化 PostgreSQL 数据库（检查表是否存在，不存在则创建）"""
        if self._postgres_initialized:
            return  # 已经初始化过，跳过
        
        sql_file = Path(__file__).parent / "init_db_postgres.sql"
        
        if not sql_file.exists():
            raise FileNotFoundError(f"PostgreSQL 初始化脚本不存在: {sql_file}")
        
        # 读取 SQL 脚本
        with open(sql_file, 'r', encoding='utf-8') as f:
            sql_script = f.read()
        
        # 执行初始化（PostgreSQL 支持 IF NOT EXISTS）
        # 注意：这里直接创建连接，而不是调用 get_connection()，避免递归调用
        try:
            # 直接创建连接，避免递归调用 get_connection()
            conn = psycopg2.connect(config.DATABASE_URL)
            cursor = conn.cursor()
            # 执行整个脚本
            cursor.execute(sql_script)
            conn.commit()
            cursor.close()
            conn.close()
            self._postgres_initialized = True
        except psycopg2.OperationalError as e:
            # 连接错误，不标记为已初始化，下次重试
            error_msg = str(e).lower()
            if "could not translate host name" in error_msg or "nodename nor servname" in error_msg:
                raise ConnectionError(
                    f"无法连接到 Supabase PostgreSQL 数据库。\n"
                    f"错误: DNS 解析失败，无法解析主机名。\n"
                    f"请检查:\n"
                    f"  1. 网络连接是否正常\n"
                    f"  2. DATABASE_URL 中的主机名是否正确\n"
                    f"  3. 防火墙是否阻止了连接\n"
                    f"  4. 如果暂时无法连接，可以设置 DATABASE_MODE=local 使用本地 SQLite\n"
                    f"\n原始错误: {str(e)}"
                )
            elif "connection refused" in error_msg:
                raise ConnectionError(
                    f"无法连接到 Supabase PostgreSQL 数据库。\n"
                    f"错误: 连接被拒绝。\n"
                    f"请检查:\n"
                    f"  1. DATABASE_URL 中的端口号是否正确（默认 5432）\n"
                    f"  2. Supabase 项目是否已暂停（免费版会暂停）\n"
                    f"  3. 防火墙是否阻止了连接\n"
                    f"\n原始错误: {str(e)}"
                )
            elif "password authentication failed" in error_msg:
                raise ConnectionError(
                    f"无法连接到 Supabase PostgreSQL 数据库。\n"
                    f"错误: 密码认证失败。\n"
                    f"请检查 DATABASE_URL 中的密码是否正确。\n"
                    f"\n原始错误: {str(e)}"
                )
            else:
                raise ConnectionError(
                    f"无法连接到 Supabase PostgreSQL 数据库。\n"
                    f"错误: {str(e)}\n"
                    f"请检查 DATABASE_URL 配置是否正确。"
                )
        except Exception as e:
            # 如果表已存在，忽略错误（CREATE TABLE IF NOT EXISTS 应该不会报错）
            error_msg = str(e).lower()
            if "already exists" not in error_msg and "duplicate" not in error_msg:
                # 其他错误需要抛出
                raise ConnectionError(f"PostgreSQL 初始化失败: {str(e)}")
            else:
                # 表已存在，标记为已初始化
                self._postgres_initialized = True
    
    def get_connection(self) -> Union[sqlite3.Connection, 'psycopg2.extensions.connection']:
        """获取数据库连接（从连接池获取或创建新连接）"""
        if self.db_type == "postgresql":
            if not PSYCOPG2_AVAILABLE:
                raise ImportError("使用 PostgreSQL 需要安装 psycopg2-binary")
            
            # 延迟初始化：第一次连接时初始化连接池和表结构
            if self._connection_pool is None:
                self._init_connection_pool()
            
            if not self._postgres_initialized:
                self._init_postgres_database()
            
            # 从连接池获取连接
            try:
                conn = self._connection_pool.getconn()
                
                # 检查连接是否有效
                if not self._is_connection_alive(conn):
                    # 连接失效，关闭并创建新连接
                    try:
                        conn.close()
                    except:
                        pass
                    # 创建新连接（不通过连接池，直接创建）
                    conn = psycopg2.connect(config.DATABASE_URL)
                
                return conn
            except pool.PoolError as e:
                # 连接池错误（如连接池已满），尝试直接创建连接
                try:
                    return psycopg2.connect(config.DATABASE_URL)
                except psycopg2.OperationalError as op_err:
                    # 处理连接错误
                    self._handle_postgres_error(op_err)
            except psycopg2.OperationalError as e:
                self._handle_postgres_error(e)
            except Exception as e:
                raise ConnectionError(f"数据库连接失败: {str(e)}")
        else:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row  # 返回字典式行
            return conn
    
    def _handle_postgres_error(self, e: Exception):
        """处理 PostgreSQL 连接错误"""
        error_msg = str(e).lower()
        if "could not translate host name" in error_msg or "nodename nor servname" in error_msg:
            raise ConnectionError(
                f"无法连接到 Supabase PostgreSQL 数据库。\n"
                f"错误: DNS 解析失败，无法解析主机名。\n"
                f"请检查:\n"
                f"  1. 网络连接是否正常\n"
                f"  2. DATABASE_URL 中的主机名是否正确\n"
                f"  3. 防火墙是否阻止了连接\n"
                f"  4. 如果暂时无法连接，可以设置 DATABASE_MODE=local 使用本地 SQLite\n"
                f"\n原始错误: {str(e)}"
            )
        elif "connection refused" in error_msg:
            raise ConnectionError(
                f"无法连接到 Supabase PostgreSQL 数据库。\n"
                f"错误: 连接被拒绝。\n"
                f"请检查:\n"
                f"  1. DATABASE_URL 中的端口号是否正确（默认 5432）\n"
                f"  2. Supabase 项目是否已暂停（免费版会暂停）\n"
                f"  3. 防火墙是否阻止了连接\n"
                f"\n原始错误: {str(e)}"
            )
        elif "password authentication failed" in error_msg:
            raise ConnectionError(
                f"无法连接到 Supabase PostgreSQL 数据库。\n"
                f"错误: 密码认证失败。\n"
                f"请检查 DATABASE_URL 中的密码是否正确。\n"
                f"\n原始错误: {str(e)}"
            )
        else:
            raise ConnectionError(
                f"无法连接到 Supabase PostgreSQL 数据库。\n"
                f"错误: {str(e)}\n"
                f"请检查 DATABASE_URL 配置是否正确。"
            )
    
    def return_connection(self, conn):
        """归还连接到池（仅 PostgreSQL）"""
        if self.db_type == "postgresql" and self._connection_pool is not None:
            try:
                # 检查连接是否有效
                if self._is_connection_alive(conn):
                    # 连接有效，归还到池
                    self._connection_pool.putconn(conn)
                else:
                    # 连接失效，关闭但不归还
                    try:
                        conn.close()
                    except:
                        pass
            except Exception as e:
                # 归还失败，尝试关闭连接
                try:
                    conn.close()
                except:
                    pass
                # 记录错误但不抛出（避免影响正常流程）
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"归还连接到池失败: {str(e)}")
                # 提供更友好的错误提示
                error_msg = str(e).lower()
                if "could not translate host name" in error_msg or "nodename nor servname" in error_msg:
                    raise ConnectionError(
                        f"无法连接到 Supabase PostgreSQL 数据库。\n"
                        f"错误: DNS 解析失败，无法解析主机名。\n"
                        f"请检查:\n"
                        f"  1. 网络连接是否正常\n"
                        f"  2. DATABASE_URL 中的主机名是否正确\n"
                        f"  3. 防火墙是否阻止了连接\n"
                        f"  4. 如果暂时无法连接，可以设置 DATABASE_MODE=local 使用本地 SQLite\n"
                        f"\n原始错误: {error_msg}"
                    )
                elif "connection refused" in error_msg.lower():
                    raise ConnectionError(
                        f"无法连接到 Supabase PostgreSQL 数据库。\n"
                        f"错误: 连接被拒绝。\n"
                        f"请检查:\n"
                        f"  1. DATABASE_URL 中的端口号是否正确（默认 5432）\n"
                        f"  2. Supabase 项目是否已暂停（免费版会暂停）\n"
                        f"  3. 防火墙是否阻止了连接\n"
                        f"\n原始错误: {error_msg}"
                    )
                elif "password authentication failed" in error_msg.lower():
                    raise ConnectionError(
                        f"无法连接到 Supabase PostgreSQL 数据库。\n"
                        f"错误: 密码认证失败。\n"
                        f"请检查 DATABASE_URL 中的密码是否正确。\n"
                        f"\n原始错误: {error_msg}"
                    )
                else:
                    raise ConnectionError(
                        f"无法连接到 Supabase PostgreSQL 数据库。\n"
                        f"错误: {error_msg}\n"
                        f"请检查 DATABASE_URL 配置是否正确。"
                    )
            except Exception as e:
                raise ConnectionError(f"数据库连接失败: {str(e)}")
        else:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row  # 返回字典式行
            return conn
    
    @contextmanager
    def get_cursor(self):
        """上下文管理器：获取游标并自动提交/关闭（连接归还到池）"""
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            
            # PostgreSQL 使用 RealDictCursor 返回字典格式
            if self.db_type == "postgresql":
                cursor = conn.cursor(cursor_factory=RealDictCursor)
            else:
                cursor = conn.cursor()
            
            yield cursor
            conn.commit()
        except ConnectionError:
            # 连接错误，直接抛出，不执行 rollback（因为连接可能根本没有建立）
            if conn and self.db_type == "postgresql":
                try:
                    conn.rollback()
                except:
                    pass
            raise
        except Exception as e:
            # 其他错误，执行 rollback
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            raise e
        finally:
            if cursor:
                try:
                    cursor.close()
                except:
                    pass
            if conn:
                if self.db_type == "postgresql":
                    # PostgreSQL: 归还连接到池（不关闭）
                    self.return_connection(conn)
                else:
                    # SQLite: 关闭连接
                    try:
                        conn.close()
                    except:
                        pass
    
    def _convert_params(self, query: str, params: tuple = ()):
        """
        转换 SQL 参数占位符
        SQLite 使用 ?，PostgreSQL 使用 %s
        """
        if self.db_type == "postgresql":
            # 将 ? 替换为 %s
            query = query.replace('?', '%s')
        return query, params
    
    def execute_query(self, query: str, params: tuple = ()):
        """
        执行查询（SELECT）
        
        Returns:
            SQLite: Row 对象列表
            PostgreSQL: 字典列表
        """
        # 提取查询类型（简化，只取前几个关键字）
        query_type = query.strip().split()[0].upper() if query.strip() else "UNKNOWN"
        details = f"type={query_type}, params_count={len(params)}"
        
        with monitor_database("execute_query", details):
            query, params = self._convert_params(query, params)
            with self.get_cursor() as cursor:
                cursor.execute(query, params)
                results = cursor.fetchall()
                
                # PostgreSQL RealDictCursor 返回字典，SQLite Row 已经是字典式
                if self.db_type == "postgresql":
                    result_list = [dict(row) for row in results]
                    # 更新详情，包含结果数量
                    return result_list
                else:
                    # SQLite Row 对象可以像字典一样访问
                    return results
    
    def execute_one(self, query: str, params: tuple = ()):
        """
        执行查询并返回一条结果
        
        Returns:
            SQLite: Row 对象
            PostgreSQL: 字典
        """
        query_type = query.strip().split()[0].upper() if query.strip() else "UNKNOWN"
        details = f"type={query_type}, params_count={len(params)}"
        
        with monitor_database("execute_one", details):
            query, params = self._convert_params(query, params)
            with self.get_cursor() as cursor:
                cursor.execute(query, params)
                result = cursor.fetchone()
                
                if result is None:
                    return None
                
                # PostgreSQL 返回字典，SQLite 返回 Row
                if self.db_type == "postgresql":
                    return dict(result)
                else:
                    return result
    
    def execute_update(self, query: str, params: tuple = ()):
        """执行更新（INSERT/UPDATE/DELETE）"""
        query_type = query.strip().split()[0].upper() if query.strip() else "UNKNOWN"
        details = f"type={query_type}, params_count={len(params)}"
        
        with monitor_database("execute_update", details):
            query, params = self._convert_params(query, params)
            with self.get_cursor() as cursor:
                cursor.execute(query, params)
                rowcount = cursor.rowcount
                return rowcount
    
    def execute_insert(self, query: str, params: tuple = ()):
        """
        执行插入并返回插入的 ID
        
        Returns:
            SQLite: lastrowid
            PostgreSQL: 使用 RETURNING 子句获取 ID
        """
        query_type = query.strip().split()[0].upper() if query.strip() else "UNKNOWN"
        details = f"type={query_type}, params_count={len(params)}"
        
        with monitor_database("execute_insert", details):
            query, params = self._convert_params(query, params)
            
            if self.db_type == "postgresql":
                # PostgreSQL 需要在查询中添加 RETURNING 子句
                # 如果查询中没有 RETURNING，尝试添加
                if "RETURNING" not in query.upper():
                    # 尝试提取表名和主键（简单实现）
                    # 实际使用中，建议在 SQL 中显式添加 RETURNING
                    with self.get_cursor() as cursor:
                        cursor.execute(query, params)
                        # 对于 PostgreSQL，如果没有 RETURNING，需要查询序列
                        # 这里简化处理，返回 0（实际应该根据表结构查询）
                        return 0
                else:
                    with self.get_cursor() as cursor:
                        cursor.execute(query, params)
                        result = cursor.fetchone()
                        if result:
                            # 返回第一个字段的值（通常是 ID）
                            return list(result.values())[0] if isinstance(result, dict) else result[0]
                        return 0
            else:
                # SQLite
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


def close_db_manager():
    """关闭数据库管理器（关闭连接池）"""
    global _db_manager
    if _db_manager is not None and _db_manager._connection_pool is not None:
        try:
            _db_manager._connection_pool.closeall()
        except:
            pass
    _db_manager = None


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

