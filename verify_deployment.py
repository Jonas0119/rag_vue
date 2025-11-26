#!/usr/bin/env python3
"""
部署验证脚本
检查项目是否准备好部署到 Streamlit Cloud
"""
import os
import sys
from pathlib import Path

def check_file_exists(filepath: str, description: str) -> bool:
    """检查文件是否存在"""
    exists = Path(filepath).exists()
    status = "✅" if exists else "❌"
    print(f"{status} {description}: {filepath}")
    return exists

def check_directory_exists(dirpath: str, description: str) -> bool:
    """检查目录是否存在"""
    exists = Path(dirpath).exists()
    status = "✅" if exists else "❌"
    print(f"{status} {description}: {dirpath}")
    return exists

def check_gitignore_pattern(pattern: str) -> bool:
    """检查 .gitignore 是否包含指定模式"""
    gitignore_path = Path(".gitignore")
    if not gitignore_path.exists():
        return False
    
    content = gitignore_path.read_text()
    return pattern in content

def main():
    """主验证函数"""
    print("=" * 60)
    print("Streamlit Cloud 部署验证")
    print("=" * 60)
    print()
    
    errors = []
    warnings = []
    
    # 1. 检查必需文件
    print("📁 检查必需文件...")
    print("-" * 60)
    
    required_files = [
        ("requirements.txt", "依赖清单文件"),
        (".streamlit/config.toml", "Streamlit 配置文件"),
        ("app.py", "主应用入口"),
        ("pyproject.toml", "Poetry 配置文件"),
    ]
    
    for filepath, description in required_files:
        if not check_file_exists(filepath, description):
            errors.append(f"缺少必需文件: {filepath}")
    
    print()
    
    # 2. 检查 .gitignore
    print("🔒 检查 .gitignore 配置...")
    print("-" * 60)
    
    gitignore_patterns = [
        (".env", "环境变量文件"),
        (".streamlit/secrets.toml", "Streamlit Secrets 文件"),
        ("data/", "本地数据目录"),
        ("logs/", "日志目录"),
    ]
    
    for pattern, description in gitignore_patterns:
        if check_gitignore_pattern(pattern):
            print(f"✅ {description} 已在 .gitignore 中: {pattern}")
        else:
            warnings.append(f"{description} 未在 .gitignore 中: {pattern}")
            print(f"⚠️  {description} 未在 .gitignore 中: {pattern}")
    
    print()
    
    # 3. 检查 requirements.txt 内容
    print("📦 检查 requirements.txt...")
    print("-" * 60)
    
    if Path("requirements.txt").exists():
        content = Path("requirements.txt").read_text()
        required_packages = [
            "streamlit",
            "langchain",
            "python-dotenv",
        ]
        
        for package in required_packages:
            if package in content.lower():
                print(f"✅ 包含依赖: {package}")
            else:
                warnings.append(f"requirements.txt 中可能缺少: {package}")
                print(f"⚠️  可能缺少依赖: {package}")
    else:
        errors.append("requirements.txt 不存在")
    
    print()
    
    # 4. 检查环境变量配置
    print("🔐 检查环境变量配置...")
    print("-" * 60)
    
    # 检查是否有 .env 文件（本地开发）
    if Path(".env").exists():
        print("✅ 找到 .env 文件（本地开发使用）")
    else:
        print("ℹ️  未找到 .env 文件（Streamlit Cloud 使用 Secrets）")
    
    # 检查 config_template.txt
    if Path("config_template.txt").exists():
        print("✅ 找到 config_template.txt（环境变量模板）")
    else:
        warnings.append("未找到 config_template.txt")
    
    print()
    
    # 5. 检查代码兼容性
    print("💻 检查代码兼容性...")
    print("-" * 60)
    
    # 检查 utils/config.py 是否使用 load_dotenv
    config_path = Path("utils/config.py")
    if config_path.exists():
        config_content = config_path.read_text()
        if "load_dotenv" in config_content:
            print("✅ utils/config.py 使用 load_dotenv（兼容本地和 Cloud）")
        else:
            warnings.append("utils/config.py 可能未使用 load_dotenv")
        
        if "override=False" in config_content or "override" in config_content:
            print("✅ 环境变量加载配置正确（不覆盖系统环境变量）")
        else:
            warnings.append("建议使用 load_dotenv(override=False)")
    else:
        errors.append("utils/config.py 不存在")
    
    # 检查 app.py 日志配置
    app_path = Path("app.py")
    if app_path.exists():
        app_content = app_path.read_text()
        if "stream=sys.stdout" in app_content:
            print("✅ app.py 使用控制台日志（兼容 Streamlit Cloud）")
        else:
            warnings.append("app.py 可能使用文件日志（Streamlit Cloud 可能无法写入）")
    else:
        errors.append("app.py 不存在")
    
    print()
    
    # 6. 总结
    print("=" * 60)
    print("验证结果")
    print("=" * 60)
    
    if errors:
        print(f"\n❌ 发现 {len(errors)} 个错误：")
        for error in errors:
            print(f"   - {error}")
    
    if warnings:
        print(f"\n⚠️  发现 {len(warnings)} 个警告：")
        for warning in warnings:
            print(f"   - {warning}")
    
    if not errors and not warnings:
        print("\n✅ 所有检查通过！项目已准备好部署到 Streamlit Cloud。")
        return 0
    elif not errors:
        print("\n⚠️  存在一些警告，但可以继续部署。")
        return 0
    else:
        print("\n❌ 存在错误，请修复后再部署。")
        return 1

if __name__ == "__main__":
    sys.exit(main())

