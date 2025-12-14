"""
用户服务层，用于获取用户信息，供缓存层调用。
"""

from backend.database.user_dao import UserDAO

class UserService:
    def __init__(self):
        self.dao = UserDAO()

    def get_user_by_id(self, user_id: int):
        """返回 User 对象（或 None）"""
        return self.dao.get_user_by_id(user_id)

    def get_user_by_username(self, username: str):
        return self.dao.get_user_by_username(username)

    def get_user_by_email(self, email: str):
        return self.dao.get_user_by_email(email)

def get_user_service() -> UserService:
    """获取全局用户服务实例（不做缓存，轻量）"""
    return UserService()
