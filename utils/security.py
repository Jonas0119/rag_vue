"""
安全工具 - 密码加密和验证
"""
import bcrypt


def hash_password(password: str) -> str:
    """
    使用 bcrypt 加密密码
    
    Args:
        password: 明文密码
    
    Returns:
        加密后的密码 hash
    """
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """
    验证密码是否正确
    
    Args:
        password: 用户输入的密码
        password_hash: 数据库存储的密码 hash
    
    Returns:
        True 如果密码正确，否则 False
    """
    try:
        return bcrypt.checkpw(
            password.encode('utf-8'),
            password_hash.encode('utf-8')
        )
    except Exception:
        return False


def validate_password_strength(password: str, min_length: int = 6) -> tuple[bool, str]:
    """
    验证密码强度
    
    Args:
        password: 待验证的密码
        min_length: 最小长度
    
    Returns:
        (是否有效, 错误信息)
    """
    if len(password) < min_length:
        return False, f"密码长度至少需要 {min_length} 个字符"
    
    # 可以添加更多规则
    # if not any(c.isupper() for c in password):
    #     return False, "密码需要包含至少一个大写字母"
    
    # if not any(c.isdigit() for c in password):
    #     return False, "密码需要包含至少一个数字"
    
    return True, ""


def validate_username(username: str) -> tuple[bool, str]:
    """
    验证用户名格式
    
    Args:
        username: 待验证的用户名
    
    Returns:
        (是否有效, 错误信息)
    """
    if len(username) < 3:
        return False, "用户名长度至少需要 3 个字符"
    
    if len(username) > 50:
        return False, "用户名长度不能超过 50 个字符"
    
    # 只允许字母、数字、下划线
    if not username.replace('_', '').isalnum():
        return False, "用户名只能包含字母、数字和下划线"
    
    return True, ""


# 测试代码
if __name__ == "__main__":
    # 测试密码加密
    password = "test123"
    hashed = hash_password(password)
    print(f"密码: {password}")
    print(f"Hash: {hashed}")
    
    # 测试密码验证
    is_valid = verify_password(password, hashed)
    print(f"验证结果: {is_valid}")
    
    # 测试错误密码
    is_valid = verify_password("wrong", hashed)
    print(f"错误密码验证: {is_valid}")

