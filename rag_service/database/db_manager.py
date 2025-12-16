"""
数据库连接管理器 - 支持 SQLite 和 PostgreSQL
"""
import sqlite3
import os
import logging
from pathlib import Path
from typing import Optional, Union
from contextlib import contextmanager
from urllib.parse import urlparse, urlunparse

from rag_service.utils.config import config
from rag_service.utils.performance_monitor import monitor_database

logger = logging.getLogger(__name__)

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
        self._direct_connections = set()  # 存储直接创建的连接ID (用于PostgreSQL)
        
        # 记录当前使用的数据库类型
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[数据库管理器] DATABASE_MODE={config.DATABASE_MODE}, 使用数据库类型: {self.db_type}")
        
        if self.db_type == "sqlite":
            logger.info(f"[数据库管理器] SQLite 数据库路径: {self.db_path}")
            self._ensure_db_directory()
            self._init_database()
        else:
            # PostgreSQL 模式：只检查配置，不立即连接
            if not config.DATABASE_URL:
                raise ValueError("DATABASE_MODE=cloud 时，必须配置 DATABASE_URL")
            if not PSYCOPG2_AVAILABLE:
                raise ImportError("使用 PostgreSQL 需要安装 psycopg2-binary: pip install psycopg2-binary")
            logger.info(f"[数据库管理器] PostgreSQL 模式，连接字符串: postgresql://***@{urlparse(config.DATABASE_URL).hostname if config.DATABASE_URL else 'N/A'}")
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
    
    def _normalize_database_url(self, database_url: str) -> str:
        """
        规范化数据库连接 URL，添加连接参数优化连接
        
        只添加连接参数，不修改主机名或进行 IP 地址解析
        """
        try:
            # 解析 URL
            parsed = urlparse(database_url)
            
            # 添加连接参数：增加超时时间，优化连接
            if parsed.query:
                # 解析现有查询参数
                from urllib.parse import parse_qs, urlencode
                existing_params = parse_qs(parsed.query)
                # 添加或更新连接参数
                existing_params['connect_timeout'] = ['10']  # 连接超时 10 秒
                existing_params['keepalives'] = ['1']  # 启用 keepalive
                existing_params['keepalives_idle'] = ['30']  # keepalive idle 时间
                existing_params['keepalives_interval'] = ['10']  # keepalive 间隔
                existing_params['keepalives_count'] = ['5']  # keepalive 重试次数
                new_query = urlencode(existing_params, doseq=True)
            else:
                # 没有现有查询参数，直接添加
                connection_params = {
                    'connect_timeout': '10',
                    'keepalives': '1',
                    'keepalives_idle': '30',
                    'keepalives_interval': '10',
                    'keepalives_count': '5',
                }
                from urllib.parse import urlencode
                new_query = urlencode(connection_params)
            
            # 重建 URL（保持原始主机名和端口不变）
            normalized_url = urlunparse((
                parsed.scheme,
                parsed.netloc,  # 保持原始主机名和端口
                parsed.path,
                parsed.params,
                new_query,
                parsed.fragment
            ))
            
            return normalized_url
        except Exception as e:
            # 如果解析失败，返回原始 URL
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"数据库 URL 规范化失败，使用原始 URL: {str(e)}")
            return database_url
    
    def _init_connection_pool(self):
        """初始化 PostgreSQL 连接池"""
        if self._connection_pool is not None:
            return  # 连接池已创建
        
        try:
            # 规范化数据库 URL，添加连接参数
            normalized_url = self._normalize_database_url(config.DATABASE_URL)
            
            # 创建连接池
            # minconn: 最小连接数（保持活跃连接）
            # maxconn: 最大连接数（峰值并发）
            # 注意：如果连接池创建失败，会在 get_connection 中降级为直接连接
            self._connection_pool = pool.SimpleConnectionPool(
                minconn=1,  # 减少最小连接数，避免初始化时连接过多
                maxconn=5,  # 减少最大连接数，适合 Streamlit Cloud 环境
                dsn=normalized_url
            )
            
            if self._connection_pool is None:
                raise ConnectionError("无法创建 PostgreSQL 连接池")
        except Exception as e:
            # 连接池创建失败，但不立即抛出异常
            # 在 get_connection 中会尝试直接连接作为降级方案
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"PostgreSQL 连接池创建失败，将使用直接连接: {str(e)}")
            # 不抛出异常，允许降级到直接连接
            self._connection_pool = None
    
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
            # 规范化数据库 URL
            normalized_url = self._normalize_database_url(config.DATABASE_URL)
            # 直接创建连接，避免递归调用 get_connection()
            conn = psycopg2.connect(normalized_url)
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
        # SQLite 模式：直接返回 SQLite 连接
        if self.db_type == "sqlite":
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row  # 返回字典式行
            return conn
        
        # PostgreSQL 模式
        if not PSYCOPG2_AVAILABLE:
            raise ImportError("使用 PostgreSQL 需要安装 psycopg2-binary")
        
        # 延迟初始化：第一次连接时初始化连接池和表结构
        if self._connection_pool is None:
            self._init_connection_pool()
        
        if not self._postgres_initialized:
            self._init_postgres_database()
        
        # 规范化数据库 URL
        normalized_url = self._normalize_database_url(config.DATABASE_URL)
        
        # 如果连接池不存在或创建失败，使用直接连接
        if self._connection_pool is None:
            # 降级到直接连接
            try:
                conn = psycopg2.connect(normalized_url)
                self._direct_connections.add(id(conn))  # 记录直接连接ID
                return conn
            except psycopg2.OperationalError as op_err:
                self._handle_postgres_error(op_err)
        
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
                conn = psycopg2.connect(normalized_url)
                self._direct_connections.add(id(conn))  # 记录为直接连接
            
            return conn
        except pool.PoolError as e:
            # 连接池错误（如连接池已满），尝试直接创建连接
            try:
                conn = psycopg2.connect(normalized_url)
                self._direct_connections.add(id(conn))  # 记录为直接连接
                return conn
            except psycopg2.OperationalError as op_err:
                # 处理连接错误
                self._handle_postgres_error(op_err)
        except psycopg2.OperationalError as e:
            self._handle_postgres_error(e)
        except Exception as e:
            # 如果连接池失败，尝试直接连接作为降级方案
            try:
                conn = psycopg2.connect(normalized_url)
                self._direct_connections.add(id(conn))  # 记录为直接连接
                return conn
            except psycopg2.OperationalError as op_err:
                self._handle_postgres_error(op_err)
            raise ConnectionError(f"数据库连接失败: {str(e)}")
    
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
        # SQLite 模式下不需要归还连接（连接已在 get_cursor 中关闭）
        if self.db_type != "postgresql":
            return
        
        # 如果没有连接或连接已关闭，直接返回
        if conn is None:
            return
        
        try:
            if conn.closed:
                return
        except:
            pass
        
        # PostgreSQL 模式：检查连接是否是直接创建的
        conn_id = id(conn)
        is_direct_connection = conn_id in self._direct_connections
        
        # 如果连接池不存在，或者连接是直接创建的，直接关闭
        if self._connection_pool is None or is_direct_connection:
            try:
                if not conn.closed:
                    conn.close()
                # 从直接连接集合中移除
                self._direct_connections.discard(conn_id)
            except:
                pass
            return
        
        # 尝试归还到连接池
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
            # 归还失败（可能是 "trying to put unkeyed connection" 错误）
            # 直接关闭连接
            error_msg = str(e).lower()
            if "unkeyed connection" in error_msg or "not from this pool" in error_msg:
                # 这是直接创建的连接，不能归还到池，直接关闭
                try:
                    if not conn.closed:
                        conn.close()
                    # 记录到直接连接集合（以防之前漏记）
                    self._direct_connections.discard(conn_id)
                except:
                    pass
            else:
                # 其他错误，记录并关闭连接
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"归还连接到池失败: {str(e)}")
                try:
                    if not conn.closed:
                        conn.close()
                except:
                    pass
    
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
        
        # 提取表名（简化版）
        table_name = "unknown"
        query_lower = query.lower()
        if "from" in query_lower:
            parts = query_lower.split("from")[1].strip().split()
            if parts:
                table_name = parts[0].strip().replace("`", "").replace('"', '')
        elif "into" in query_lower:
            parts = query_lower.split("into")[1].strip().split()
            if parts:
                table_name = parts[0].strip().replace("`", "").replace('"', '')
        elif "update" in query_lower:
            parts = query_lower.split("update")[1].strip().split()
            if parts:
                table_name = parts[0].strip().replace("`", "").replace('"', '')
        
        # 截取查询预览（前100个字符）
        query_preview = query.strip()[:100].replace('\n', ' ')
        
        details = f"type={query_type}, params_count={len(params)}"
        
        with monitor_database("execute_query", details):
            query, params = self._convert_params(query, params)
            with self.get_cursor() as cursor:
                cursor.execute(query, params)
                results = cursor.fetchall()
                
                # PostgreSQL RealDictCursor 返回字典，SQLite Row 已经是字典式
                if self.db_type == "postgresql":
                    result_list = [dict(row) for row in results]
                    logger.debug(f"[数据库] {query_type} {table_name} → {len(result_list)} 行 | {query_preview}")
                    return result_list
                else:
                    # SQLite Row 对象可以像字典一样访问
                    logger.debug(f"[数据库] {query_type} {table_name} → {len(results)} 行 | {query_preview}")
                    return results
    
    def execute_one(self, query: str, params: tuple = ()):
        """
        执行查询并返回一条结果
        
        Returns:
            SQLite: Row 对象
            PostgreSQL: 字典
        """
        query_type = query.strip().split()[0].upper() if query.strip() else "UNKNOWN"
        
        # 提取表名
        table_name = "unknown"
        query_lower = query.lower()
        if "from" in query_lower:
            parts = query_lower.split("from")[1].strip().split()
            if parts:
                table_name = parts[0].strip().replace("`", "").replace('"', '')
        
        # 截取查询预览
        query_preview = query.strip()[:100].replace('\n', ' ')
        
        details = f"type={query_type}, params_count={len(params)}"
        
        with monitor_database("execute_one", details):
            query, params = self._convert_params(query, params)
            with self.get_cursor() as cursor:
                cursor.execute(query, params)
                result = cursor.fetchone()
                
                if result is None:
                    logger.debug(f"[数据库] {query_type} {table_name} → 0 行 | {query_preview}")
                    return None
                
                # PostgreSQL 返回字典，SQLite 返回 Row
                logger.debug(f"[数据库] {query_type} {table_name} → 1 行 | {query_preview}")
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
    
    # 检查是否需要重新创建实例（配置变更时）
    if _db_manager is not None:
        # 检查数据库类型是否匹配当前配置
        expected_db_type = "postgresql" if config.DATABASE_MODE == "cloud" else "sqlite"
        if _db_manager.db_type != expected_db_type:
            # 配置已变更，关闭旧实例并创建新实例
            try:
                if _db_manager._connection_pool is not None:
                    _db_manager._connection_pool.closeall()
            except:
                pass
            _db_manager = None
    
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

