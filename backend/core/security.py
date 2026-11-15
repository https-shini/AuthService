"""Primitivas de segurança: hash de senha (bcrypt) e JWT de acesso.

O ciclo de vida das sessões (refresh, revogação) fica em
`backend/services/token_service.py`; aqui só se assina e se lê o token.
"""

import secrets
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import bcrypt
from jose import JWTError, jwt

from backend.core.config import settings

ACCESS_TOKEN_TYPE = "access"

# Hash de uma senha aleatória, usado quando o e-mail não existe: o login
# gasta o mesmo tempo de bcrypt com ou sem usuário, o que impede descobrir
# e-mails cadastrados pelo tempo de resposta.
_DUMMY_HASH = bcrypt.hashpw(secrets.token_bytes(16), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def burn_password_check(plain_password: str) -> None:
    """Executa um bcrypt descartável (mesmo custo de um login real)."""
    bcrypt.checkpw(plain_password.encode("utf-8"), _DUMMY_HASH.encode("utf-8"))


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def encode_access_token(*, subject: str, session_id: str, jti: str, issued_at: datetime, expires_at: datetime) -> str:
    claims = {
        "sub": subject,
        "sid": session_id,
        "jti": jti,
        "type": ACCESS_TOKEN_TYPE,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Payload de um access token válido, ou None.

    Recusa assinatura inválida, expiração vencida, algoritmo diferente do
    configurado e tokens sem as claims obrigatórias (inclusive tokens do
    formato antigo, que não tinham `jti`/`sid` e não podem ser revogados).
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None
    if payload.get("type") != ACCESS_TOKEN_TYPE:
        return None
    if not all(isinstance(payload.get(k), str) and payload[k] for k in ("sub", "sid", "jti")):
        return None
    if not isinstance(payload.get("exp"), int):
        return None
    return payload


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
