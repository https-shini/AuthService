from typing import Optional


class User:
    def __init__(self, id: Optional[int], email: str, hashed_password: str):
        self.id = id
        self.email = email
        self.hashed_password = hashed_password
