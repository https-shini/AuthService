from fastapi import HTTPException, status
from backend.repositories.user_repository import UserRepository
from backend.schemas.user_schemas import UserCreate, UserOut
from backend.models.user import User
from backend.core.security import get_password_hash, verify_password


class AuthService:
    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

    def register_user(self, user_data: UserCreate) -> UserOut:
        if self.user_repository.exists_by_email(user_data.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email já registrado"
            )
        hashed_password = get_password_hash(user_data.password)
        new_user = User(id=None, email=user_data.email, hashed_password=hashed_password)
        created_user = self.user_repository.save(new_user)
        return UserOut(id=created_user.id, email=created_user.email)

    def authenticate_user(self, email: str, password: str) -> User:
        user = self.user_repository.get_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email ou senha incorretos",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user
    