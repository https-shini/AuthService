from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from backend.api.auth_routes import router as auth_router
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
