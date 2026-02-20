from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from backend.schemas.user_schemas import UserCreate, UserOut, Token
from backend.services.auth_service import AuthService
from backend.dependencies.dependencies import get_user_repository, get_current_user
from backend.core.security import create_access_token
from backend.core.logger import get_logger
from backend.models.user import User

router = APIRouter()
logger = get_logger(__name__)


def get_auth_service(
    user_repository=Depends(get_user_repository),
) -> AuthService:
    return AuthService(user_repository)


@router.post("/register", response_model=UserOut, summary="Registrar um novo usuário")
async def register_user(
    user_data: UserCreate,
    auth_service: AuthService = Depends(get_auth_service),
):
    logger.info(f"Tentativa de registro para o email: {user_data.email}")
    try:
        new_user = auth_service.register_user(user_data)
        logger.info(f"Usuário {new_user.email} registrado com sucesso.")
        return new_user
    except HTTPException as e:
        logger.warning(f"Falha no registro para o email {user_data.email}: {e.detail}")
        raise e


@router.post("/token", response_model=Token, summary="Autenticar usuário e obter token JWT")
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthService = Depends(get_auth_service),
):
    logger.info(f"Tentativa de login para o email: {form_data.username}")
    try:
        user = auth_service.authenticate_user(form_data.username, form_data.password)
        access_token = create_access_token(data={"sub": user.email})
        logger.info(f"Login bem-sucedido para o email: {user.email}")
        return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException as e:
        logger.warning(f"Falha no login para o email {form_data.username}: {e.detail}")
        raise e


@router.get("/health", summary="Verificar o status da API")
async def health_check():
    logger.info("Health check solicitado.")
    return {"status": "ok", "message": "Serviço de Autenticação no ar!"}


@router.get("/me", response_model=UserOut, summary="Obter informações do usuário autenticado")
async def read_users_me(current_user: User = Depends(get_current_user)):
    logger.info(f"Acesso à rota /me pelo usuário: {current_user.email}")
    return UserOut(id=current_user.id, email=current_user.email)
