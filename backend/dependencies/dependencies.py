from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from backend.repositories.user_repository import UserRepository
from backend.core.security import decode_access_token
from backend.models.user import User

user_repository_instance = UserRepository()


def get_user_repository() -> UserRepository:
    return user_repository_instance


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    user_repo: UserRepository = Depends(get_user_repository),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    email: str = payload.get("sub")
    if email is None:
        raise credentials_exception
    user = user_repo.get_by_email(email)
    if user is None:
        raise credentials_exception
    return user
