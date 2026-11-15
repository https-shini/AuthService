from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from backend.core.config import settings
from backend.core.network import get_client_ip
from backend.core.rate_limit import LoginLimits, LoginRateLimiter
from backend.models.user import User
from backend.repositories.user_repository import UserRepository
from backend.services.token_service import TokenService

# Singletons do processo (estado em memória, como o repositório de usuários).
user_repository_instance = UserRepository()
token_service_instance = TokenService(settings)
login_rate_limiter_instance = LoginRateLimiter(
    LoginLimits(
        ip_max_attempts=settings.LOGIN_IP_MAX_ATTEMPTS,
        ip_window=settings.LOGIN_IP_WINDOW_SECONDS,
        account_ip_max_failures=settings.LOGIN_ACCOUNT_IP_MAX_FAILURES,
        account_max_failures=settings.LOGIN_ACCOUNT_MAX_FAILURES,
        failure_window=settings.LOGIN_FAILURE_WINDOW_SECONDS,
        lockout=settings.LOGIN_LOCKOUT_SECONDS,
    )
)


def get_user_repository() -> UserRepository:
    return user_repository_instance


def get_token_service() -> TokenService:
    return token_service_instance


def get_login_rate_limiter() -> LoginRateLimiter:
    return login_rate_limiter_instance


def get_request_ip(request: Request) -> str:
    return get_client_ip(request, settings.TRUSTED_PROXY_HOPS)


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

CREDENTIALS_ERROR = "Não foi possível validar as credenciais"


def _credentials_exception() -> HTTPException:
    # Mensagem genérica de propósito: não diz se o token expirou, foi
    # adulterado ou revogado, e nunca ecoa o token.
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=CREDENTIALS_ERROR,
        headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
    )


def get_access_payload(
    token: str = Depends(oauth2_scheme),
    tokens: TokenService = Depends(get_token_service),
) -> dict:
    payload = tokens.validate_access(token)
    if payload is None:
        raise _credentials_exception()
    return payload


def get_optional_access_payload(
    token: Optional[str] = Depends(optional_oauth2_scheme),
    tokens: TokenService = Depends(get_token_service),
) -> Optional[dict]:
    return tokens.validate_access(token) if token else None


def get_current_user(
    payload: dict = Depends(get_access_payload),
    user_repo: UserRepository = Depends(get_user_repository),
) -> User:
    user = user_repo.get_by_email(payload["sub"])
    if user is None:
        raise _credentials_exception()
    return user
