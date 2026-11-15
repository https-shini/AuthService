import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from backend.api.auth_routes import router as auth_router
from backend.core.config import settings
from backend.core.logger import get_logger
from backend.core.security_headers import apply_security_headers

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Resumo da configuração SEM segredos.
    logger.info(
        "Aplicação FastAPI iniciada (alg=%s, access=%s min, refresh=%s min, "
        "cookie_secure=%s, proxy_hops=%s, hsts=%s).",
        settings.ALGORITHM,
        settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        settings.REFRESH_TOKEN_EXPIRE_MINUTES,
        settings.COOKIE_SECURE,
        settings.TRUSTED_PROXY_HOPS,
        settings.HSTS_ENABLED,
    )
    yield
    logger.info("Aplicação FastAPI encerrada.")


app = FastAPI(
    title="Serviço de Autenticação",
    description=(
        "API de usuários e autenticação com JWT (access token Bearer), refresh "
        "token rotativo em cookie HttpOnly e revogação de sessão. Dados em memória."
    ),
    version="2.0.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    apply_security_headers(request, response, settings)
    return response


app.include_router(auth_router, tags=["Autenticação"])

# Caminho absoluto baseado em /code (WORKDIR do Docker)
static_dir = os.path.join("/code", "frontend")

# Fallback para desenvolvimento local
if not os.path.exists(static_dir):
    static_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
    static_dir = os.path.abspath(static_dir)

if os.path.exists(static_dir):
    logger.info(f"Servindo frontend de: {static_dir}")
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
else:
    logger.warning(f"Diretório frontend não encontrado: {static_dir}")
