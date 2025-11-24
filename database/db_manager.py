"""
数据库连接管理器 - 支持 SQLite 和 PostgreSQL
"""
import sqlite3
import os
import socket
from pathlib import Path
from typing import Optional, Union
from contextlib import contextmanager
from urllib.parse import urlparse, urlunparse

from utils.config import config
from utils.performance_monitor import monitor_database

# 强制使用 IPv4（解决 Streamlit Cloud IPv6 连接问题）
# 保存原始的 getaddrinfo 函数
_original_getaddrinfo = socket.getaddrinfo

def _ipv4_getaddrinfo(*args, **kwargs):
    """强制使用 IPv4 的 getaddrinfo"""
    try:
        responses = _original_getaddrinfo(*args, **kwargs)
        # 过滤掉 IPv6 地址，只返回 IPv4
        ipv4_responses = [r for r in responses if r[0] == socket.AF_INET]
        
        # 如果没有 IPv4 地址，记录警告但返回原始响应（让系统处理）
        if not ipv4_responses:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"DNS 解析未返回 IPv4 地址，主机: {args[0] if args else 'unknown'}。"
                f"返回了 {len(responses)} 个地址，但都是 IPv6。"
                f"这可能导致连接失败。"
            )
            # 如果确实没有 IPv4，返回原始响应（可能包含 IPv6，但至少不会因为空列表而失败）
            # 在实际情况下，大多数服务都同时提供 IPv4 和 IPv6
            return responses
        
        return ipv4_responses
    except Exception as e:
        # 如果出错，回退到原始函数
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"IPv4 过滤失败，使用原始 getaddrinfo: {str(e)}")
        return _original_getaddrinfo(*args, **kwargs)

# 在所有情况下强制使用 IPv4（解决 Streamlit Cloud IPv6 连接问题）
# 注意：这会影响所有 socket 连接，但可以解决 PostgreSQL 连接问题
# 由于 Streamlit Cloud 不支持 IPv6，我们总是强制使用 IPv4
# 本地环境通常也支持 IPv4，所以这个修改是安全的
try:
    # 立即替换，不检查环境（因为总是强制 IPv4 是安全的）
    socket.getaddrinfo = _ipv4_getaddrinfo
    
    # 记录日志（如果可能）
    try:
        import logging
        logger = logging.getLogger(__name__)
        logger.debug("已启用 IPv4 强制模式（过滤 IPv6 地址）")
    except:
        pass
except Exception as e:
    # 如果设置失败，记录错误但不影响其他功能
    import logging
    try:
        logger = logging.getLogger(__name__)
        logger.warning(f"无法设置 IPv4 强制模式: {str(e)}")
    except:
        pass

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
    
    def _resolve_hostname_to_ipv4(self, hostname: str) -> Optional[str]:
        """
        解析主机名为 IPv4 地址
        
        返回 IPv4 地址字符串，如果解析失败返回 None
        """
        try:
            # 使用 socket.getaddrinfo 解析，显式指定只获取 IPv4 地址
            # 注意：我们已经全局替换了 getaddrinfo 为只返回 IPv4 的版本
            # 但这里显式指定 family=socket.AF_INET 以确保只获取 IPv4
            results = _original_getaddrinfo(hostname, None, socket.AF_INET, socket.SOCK_STREAM)
            if results:
                # 获取第一个 IPv4 地址
                ipv4_address = results[0][4][0]
                import logging
                logger = logging.getLogger(__name__)
                logger.debug(f"主机名 {hostname} 解析为 IPv4 地址: {ipv4_address}")
                return ipv4_address
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"无法解析主机名 {hostname} 为 IPv4 地址: {str(e)}")
        return None
    
    def _normalize_database_url(self, database_url: str) -> str:
        """
        规范化数据库连接 URL，解决 IPv6 连接问题
        
        Streamlit Cloud 可能不支持 IPv6，需要：
        1. 手动解析主机名为 IPv4 地址，使用 IP 地址连接
        2. 添加连接参数优化连接
        """
        try:
            # 解析 URL
            parsed = urlparse(database_url)
            hostname = parsed.hostname
            
            # 如果主机名是域名（不是 IP 地址），尝试解析为 IPv4
            ipv4_address = None
            if hostname and not self._is_ip_address(hostname):
                # 尝试解析为 IPv4 地址
                ipv4_address = self._resolve_hostname_to_ipv4(hostname)
            
            # 构建新的 netloc
            netloc_parts = parsed.netloc.split('@')
            if len(netloc_parts) == 2:
                # 有用户名密码部分
                auth_part = netloc_parts[0]
                host_part = netloc_parts[1]
                
                # 提取端口
                if ':' in host_part:
                    _, port = host_part.rsplit(':', 1)
                else:
                    port = '5432'  # 默认 PostgreSQL 端口
                
                # 如果成功解析到 IPv4 地址，使用 IP 地址替换主机名
                if ipv4_address:
                    new_netloc = f"{auth_part}@{ipv4_address}:{port}"
                else:
                    # 解析失败，保持原样（但会添加连接参数）
                    new_netloc = parsed.netloc
            else:
                # 没有用户名密码部分（不太可能，但处理一下）
                if ':' in parsed.netloc:
                    _, port = parsed.netloc.rsplit(':', 1)
                else:
                    port = '5432'
                
                if ipv4_address:
                    new_netloc = f"{ipv4_address}:{port}"
                else:
                    new_netloc = parsed.netloc
            
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
            
            # 重建 URL
            normalized_url = urlunparse((
                parsed.scheme,
                new_netloc,  # 使用新的 netloc（可能包含 IPv4 地址）
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
    
    def _is_ip_address(self, host: str) -> bool:
        """检查字符串是否是 IP 地址（IPv4 或 IPv6）"""
        try:
            # 尝试解析为 IPv4
            socket.inet_aton(host)
            return True
        except socket.error:
            try:
                # 尝试解析为 IPv6
                socket.inet_pton(socket.AF_INET6, host)
                return True
            except socket.error:
                return False
    
    def _init_connection_pool(self):
        """初始化 PostgreSQL 连接池"""
        if self._connection_pool is not None:
            return  # 连接池已创建
        
        try:
            # 规范化数据库 URL，解决 IPv6 连接问题
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
        if self.db_type == "postgresql":
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
                    return psycopg2.connect(normalized_url)
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
                
                return conn
            except pool.PoolError as e:
                # 连接池错误（如连接池已满），尝试直接创建连接
                try:
                    return psycopg2.connect(normalized_url)
                except psycopg2.OperationalError as op_err:
                    # 处理连接错误
                    self._handle_postgres_error(op_err)
            except psycopg2.OperationalError as e:
                self._handle_postgres_error(e)
            except Exception as e:
                # 如果连接池失败，尝试直接连接作为降级方案
                try:
                    return psycopg2.connect(normalized_url)
                except psycopg2.OperationalError as op_err:
                    self._handle_postgres_error(op_err)
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

