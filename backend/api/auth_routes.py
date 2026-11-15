import re
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm

from backend.core.config import settings
from backend.core.cookies import CSRF_HEADER, clear_session_cookies, cookie_names, set_session_cookies
from backend.core.email import normalize_email
from backend.core.logger import get_logger
from backend.core.rate_limit import LoginRateLimiter
from backend.dependencies.dependencies import (
    get_current_user,
    get_login_rate_limiter,
    get_optional_access_payload,
    get_request_ip,
    get_token_service,
    get_user_repository,
)
from backend.models.user import User
from backend.repositories.user_repository import UserRepository
from backend.schemas.user_schemas import Token, UserCreate, UserOut
from backend.services.auth_service import AuthService
from backend.services.token_service import CsrfTokenMismatch, InvalidRefreshToken, TokenError, TokenService

router = APIRouter()
logger = get_logger(__name__)


def sanitize_log(value: str) -> str:
    """Remove caracteres de nova linha para prevenir Log Injection."""
    return re.sub(r"[\n\r]", "_", str(value))


def get_auth_service(user_repository=Depends(get_user_repository)) -> AuthService:
    return AuthService(user_repository)


def _token_body(access_token: str) -> dict:
    return {"access_token": access_token, "token_type": "bearer"}


# As rotas que rodam bcrypt são `def` (e não `async def`): o FastAPI as
# executa em thread, sem travar o event loop durante o hash.


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar um novo usuário",
    responses={400: {"description": "E-mail já registrado"}, 422: {"description": "Dados inválidos"}},
)
def register_user(user_data: UserCreate, auth_service: AuthService = Depends(get_auth_service)):
    logger.info("Tentativa de registro para o email: %s", sanitize_log(user_data.email))
    try:
        new_user = auth_service.register_user(user_data)
    except HTTPException as error:
        logger.warning("Falha no registro: %s", sanitize_log(error.detail))
        raise
    logger.info("Usuário registrado com sucesso.")
    return new_user


@router.post(
    "/token",
    response_model=Token,
    summary="Autenticar usuário e obter token JWT",
    responses={
        401: {"description": "Credenciais incorretas"},
        429: {"description": "Muitas tentativas; ver header Retry-After"},
    },
)
def login_for_access_token(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthService = Depends(get_auth_service),
    tokens: TokenService = Depends(get_token_service),
    limiter: LoginRateLimiter = Depends(get_login_rate_limiter),
    client_ip: str = Depends(get_request_ip),
):
    account = normalize_email(form_data.username)
    logger.info("Tentativa de login para o email: %s", sanitize_log(account))

    retry_after = limiter.retry_after(client_ip, account)
    if retry_after is not None:
        logger.warning("Login bloqueado por excesso de tentativas (ip=%s).", sanitize_log(client_ip))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Muitas tentativas de login. Tente novamente em {retry_after} s.",
            headers={"Retry-After": str(retry_after)},
        )

    limiter.record_attempt(client_ip)
    try:
        user = auth_service.authenticate_user(form_data.username, form_data.password)
    except HTTPException as error:
        limiter.record_failure(client_ip, account)
        logger.warning("Falha no login: %s", sanitize_log(error.detail))
        raise
    limiter.record_success(client_ip, account)

    issued = tokens.start_session(user)
    set_session_cookies(response, issued, settings)
    logger.info("Login bem-sucedido.")
    return _token_body(issued.access_token)


@router.post(
    "/refresh",
    response_model=Token,
    summary="Renovar o access token (cookie de refresh + header X-CSRF-Token)",
    responses={401: {"description": "Sessão inválida, expirada ou revogada"}, 403: {"description": "CSRF inválido"}},
)
def refresh_access_token(
    request: Request,
    csrf_token: Optional[str] = Header(default=None, alias=CSRF_HEADER),
    tokens: TokenService = Depends(get_token_service),
    user_repo: UserRepository = Depends(get_user_repository),
):
    names = cookie_names(settings)
    try:
        issued = tokens.rotate(request.cookies.get(names.refresh), csrf_token, user_repo.get_by_id)
    except TokenError as error:
        logger.warning("Refresh recusado: %s", type(error).__name__)
        failure = JSONResponse(status_code=error.status_code, content={"detail": error.detail})
        if isinstance(error, InvalidRefreshToken):
            clear_session_cookies(failure, settings)
        return failure

    response = JSONResponse(content=_token_body(issued.access_token))
    set_session_cookies(response, issued, settings)
    return response


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Encerrar a sessão no servidor",
    responses={403: {"description": "Sem Bearer válido e CSRF inválido para o cookie de refresh"}},
)
def logout(
    request: Request,
    payload: Optional[dict] = Depends(get_optional_access_payload),
    csrf_token: Optional[str] = Header(default=None, alias=CSRF_HEADER),
    tokens: TokenService = Depends(get_token_service),
):
    """Revoga a sessão: o access token apresentado e o refresh dela.

    Com Bearer válido não é preciso CSRF (o header Authorization não é
    enviado sozinho pelo navegador). Só com o cookie, o X-CSRF-Token é
    obrigatório. É idempotente: sem sessão, apenas limpa os cookies.
    """
    refresh_cookie = request.cookies.get(cookie_names(settings).refresh)
    if payload is not None:
        tokens.revoke_access(payload)
        try:
            tokens.revoke_by_refresh(refresh_cookie, csrf_token)
        except CsrfTokenMismatch:
            pass  # a sessão do Bearer já foi revogada
    elif refresh_cookie:
        try:
            tokens.revoke_by_refresh(refresh_cookie, csrf_token)
        except CsrfTokenMismatch as error:
            return JSONResponse(status_code=error.status_code, content={"detail": error.detail})

    logger.info("Logout concluído.")
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_session_cookies(response, settings)
    return response


@router.get("/health", summary="Verificar o status da API")
async def health_check():
    logger.info("Health check solicitado.")
    return {"status": "ok", "message": "Serviço de Autenticação no ar!"}


@router.get("/me", response_model=UserOut, summary="Obter informações do usuário autenticado")
async def read_users_me(current_user: User = Depends(get_current_user)):
    logger.info("Acesso à rota /me pelo usuário autenticado.")
    return UserOut(id=current_user.id, email=current_user.email, name=current_user.name)
