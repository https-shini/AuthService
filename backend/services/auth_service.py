from fastapi import HTTPException, status

from backend.core.security import burn_password_check, get_password_hash, verify_password
from backend.models.user import User
from backend.repositories.user_repository import UserRepository
from backend.schemas.user_schemas import UserCreate, UserOut

INVALID_CREDENTIALS = "Email ou senha incorretos"


class AuthService:
    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository

    def register_user(self, user_data: UserCreate) -> UserOut:
        # user_data.email já vem normalizado pelo schema; a checagem ignora
        # maiúsculas também contra contas antigas.
        if self.user_repository.exists_by_email(user_data.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email já registrado",
            )
        new_user = User(
            id=None,
            email=user_data.email,
            hashed_password=get_password_hash(user_data.password),
            name=user_data.name,
        )
        created = self.user_repository.save(new_user)
        return UserOut(id=created.id, email=created.email, name=created.name)

    def authenticate_user(self, email: str, password: str) -> User:
        user = self.user_repository.find_for_login(email)
        if user is None:
            burn_password_check(password)  # mesmo custo com ou sem usuário
            raise self._invalid()
        if not verify_password(password, user.hashed_password):
            raise self._invalid()
        return user

    @staticmethod
    def _invalid() -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_CREDENTIALS,
            headers={"WWW-Authenticate": "Bearer"},
        )
