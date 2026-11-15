from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from backend.api.auth_routes import router as auth_router
from backend.core.config import settings
from backend.core.logger import get_logger
import os

logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Aplicação FastAPI iniciada.")
    yield
    logger.info("Aplicação FastAPI encerrada.")

app = FastAPI(
    title="Serviço de Autenticação",
    description="Uma API para gerenciar usuários e autenticação com JWT (in-memory)",
    version="1.0.0",
    lifespan=lifespan,
)

_public_url = settings.PUBLIC_URL.strip().rstrip("/")
_old_host = settings.RENDER_EXTERNAL_HOSTNAME.strip().lower()


@app.middleware("http")
async def redirect_old_host(request: Request, call_next):
    """Redireciona o endereço do Render (*.onrender.com) para PUBLIC_URL.

    Só age quando as duas variáveis existem e o Host da requisição é o do
    Render; o health check interno e o desenvolvimento local não mudam.
    O 308 mantém o método e o corpo (POST /register, POST /token).
    """
    host = request.headers.get("host", "").split(":")[0].lower()
    if _public_url and _old_host and host == _old_host:
        target = _public_url + request.url.path
        if request.url.query:
            target += "?" + request.url.query
        return RedirectResponse(target, status_code=308)
    return await call_next(request)


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
