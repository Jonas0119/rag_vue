#!/usr/bin/env python3
"""
云端配置检查脚本
用于验证所有云服务配置是否完整且正确
"""
import sys
import os
from pathlib import Path

# 添加 backend 目录到路径
BACKEND_DIR = Path(__file__).parent
sys.path.insert(0, str(BACKEND_DIR.parent))

from backend.utils.config import config
from backend.utils.deployment_check import check_cloud_deployment_config

def check_dependencies():
    """检查必要的依赖包是否已安装"""
    missing_deps = []
    
    # 检查 Supabase
    if config.STORAGE_MODE == "cloud":
        try:
            import supabase
        except ImportError:
            missing_deps.append("supabase (pip install supabase)")
    
    # 检查 PostgreSQL
    if config.DATABASE_MODE == "cloud":
        try:
            import psycopg2
        except ImportError:
            missing_deps.append("psycopg2-binary (pip install psycopg2-binary)")
    
    # 检查 Pinecone
    if config.VECTOR_DB_MODE == "cloud":
        try:
            import pinecone
            import langchain_pinecone
        except ImportError:
            missing_deps.append("pinecone langchain-pinecone (pip install pinecone langchain-pinecone)")
    
    return missing_deps

def check_initialization():
    """检查云服务是否能正常初始化"""
    issues = []
    
    # 检查 Supabase Storage
    if config.STORAGE_MODE == "cloud":
        try:
            from backend.utils.supabase_storage import get_supabase_storage
            storage = get_supabase_storage()
            if storage is None:
                issues.append("❌ Supabase Storage 初始化失败（检查 SUPABASE_URL 和 SUPABASE_SERVICE_KEY）")
            else:
                print("✅ Supabase Storage 初始化成功")
        except Exception as e:
            issues.append(f"❌ Supabase Storage 初始化异常: {str(e)}")
    
    # 检查 PostgreSQL 数据库
    if config.DATABASE_MODE == "cloud":
        try:
            from backend.database.db_manager import get_db_manager
            db_manager = get_db_manager()
            # 尝试获取连接（不实际连接，只检查配置）
            if db_manager.db_type != "postgresql":
                issues.append("❌ 数据库管理器未正确配置为 PostgreSQL 模式")
            else:
                print("✅ PostgreSQL 数据库配置正确")
        except Exception as e:
            issues.append(f"❌ PostgreSQL 数据库配置异常: {str(e)}")
    
    # 检查 Pinecone（注意：这里只检查配置，不实际连接）
    if config.VECTOR_DB_MODE == "cloud":
        try:
            # 检查 Pinecone 策略是否能创建（不实际连接）
            from backend.services.vector_strategies import PineconeStrategy
            from langchain_huggingface import HuggingFaceEmbeddings
            # 只检查配置，不实际初始化（因为需要加载模型）
            if not config.PINECONE_API_KEY:
                issues.append("❌ PINECONE_API_KEY 未配置")
            elif "your_pinecone" in config.PINECONE_API_KEY:
                issues.append("❌ PINECONE_API_KEY 使用占位符值")
            else:
                print("✅ Pinecone 配置正确（未实际连接测试）")
        except Exception as e:
            issues.append(f"❌ Pinecone 配置检查异常: {str(e)}")
    
    return issues

def main():
    """主检查函数"""
    print("=" * 60)
    print("云端配置检查")
    print("=" * 60)
    print()
    
    # 显示当前配置
    print("📋 当前配置:")
    print(f"  STORAGE_MODE: {config.STORAGE_MODE}")
    print(f"  VECTOR_DB_MODE: {config.VECTOR_DB_MODE}")
    print(f"  DATABASE_MODE: {config.DATABASE_MODE}")
    print()
    
    # 检查依赖
    print("📦 检查依赖包...")
    missing_deps = check_dependencies()
    if missing_deps:
        print("❌ 缺少以下依赖包:")
        for dep in missing_deps:
            print(f"  • {dep}")
        print()
    else:
        print("✅ 所有必要的依赖包已安装")
        print()
    
    # 检查配置
    print("⚙️  检查配置...")
    is_ok, messages = check_cloud_deployment_config()
    
    errors = [m for m in messages if not m.startswith("STORAGE_MODE") and 
              not m.startswith("VECTOR_DB_MODE") and 
              not m.startswith("DATABASE_MODE") and
              not m.startswith("PINECONE_ENVIRONMENT")]
    warnings = [m for m in messages if m not in errors]
    
    if errors:
        print("❌ 配置错误:")
        for error in errors:
            print(f"  • {error}")
        print()
    
    if warnings:
        print("⚠️  配置警告:")
        for warning in warnings:
            print(f"  • {warning}")
        print()
    
    if not errors and not warnings:
        print("✅ 配置检查通过")
        print()
    
    # 检查初始化
    print("🔧 检查服务初始化...")
    init_issues = check_initialization()
    if init_issues:
        for issue in init_issues:
            print(f"  {issue}")
        print()
    
    # 总结
    print("=" * 60)
    if missing_deps or errors or init_issues:
        print("❌ 检查未通过，请修复上述问题")
        return 1
    else:
        print("✅ 所有检查通过！系统已准备好使用云端服务")
        return 0

if __name__ == "__main__":
    sys.exit(main())
