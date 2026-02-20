from typing import Dict, List, Optional
from backend.models.user import User


class UserRepository:
    def __init__(self):
        self.users: Dict[int, User] = {}
        self.next_id = 1

    def save(self, user: User) -> User:
        if user.id is None:
            user.id = self.next_id
            self.next_id += 1
        self.users[user.id] = user
        return user

    def get_by_email(self, email: str) -> Optional[User]:
        for user in self.users.values():
            if user.email == email:
                return user
        return None

    def get_by_id(self, user_id: int) -> Optional[User]:
        return self.users.get(user_id)

    def exists_by_email(self, email: str) -> bool:
        return self.get_by_email(email) is not None

    def get_all(self) -> List[User]:
        return list(self.users.values())
    