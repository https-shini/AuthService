"""Sessões, refresh tokens e revogação (em memória).

Modelo
------
Cada login abre uma SESSÃO (`sid`) com prazo absoluto
(REFRESH_TOKEN_EXPIRE_MINUTES). A sessão emite:

* access token — JWT curto (ACCESS_TOKEN_EXPIRE_MINUTES) devolvido no
  corpo da resposta e usado como `Authorization: Bearer`. Carrega `sid` e
  um `jti` único, então pode ser revogado antes de expirar;
* refresh token — valor aleatório opaco, enviado SÓ em cookie HttpOnly;
* token CSRF — valor aleatório entregue em cookie legível pelo frontend,
  que precisa devolvê-lo no header X-CSRF-Token. Fica atrelado ao refresh
  token no servidor (padrão "synchronizer token"), não basta repetir o
  cookie.

Rotação: cada uso do refresh token o invalida e emite outro (e um novo
CSRF). Reapresentar um refresh token já trocado indica cópia: fora da
janela de tolerância (REFRESH_REUSE_GRACE_SECONDS, para corridas entre abas)
a sessão inteira é revogada.

Só HASHES (SHA-256) de refresh e CSRF ficam guardados. O estado zera
quando o processo reinicia — igual aos usuários.
"""

import hashlib
import hmac
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Dict, Optional

from backend.core.config import Settings
from backend.core.security import decode_access_token, encode_access_token
from backend.models.user import User


class TokenError(Exception):
    status_code = 401
    detail = "Sessão inválida ou expirada"


class InvalidRefreshToken(TokenError):
    pass


class CsrfTokenMismatch(TokenError):
    status_code = 403
    detail = "Token CSRF ausente ou inválido"


@dataclass
class _Session:
    user_id: int
    expires_at: float
    revoked: bool = False


@dataclass
class _RefreshRecord:
    session_id: str
    csrf_hash: str
    rotated_at: Optional[float] = None


@dataclass(frozen=True)
class IssuedTokens:
    access_token: str
    access_expires_at: datetime
    refresh_token: str
    csrf_token: str
    session_id: str


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class TokenService:
    def __init__(self, settings: Settings, clock: Callable[[], float] = time.time):
        self._settings = settings
        self._clock = clock
        self._lock = threading.Lock()
        self._sessions: Dict[str, _Session] = {}
        self._refresh: Dict[str, _RefreshRecord] = {}
        self._revoked_jti: Dict[str, float] = {}

    # Emissão ----------------------------------------------------------------
    def start_session(self, user: User) -> IssuedTokens:
        now = self._clock()
        session_id = secrets.token_urlsafe(16)
        with self._lock:
            self._prune(now)
            self._sessions[session_id] = _Session(
                user_id=user.id,
                expires_at=now + self._settings.REFRESH_TOKEN_EXPIRE_MINUTES * 60,
            )
            return self._issue(user, session_id, now)

    def _issue(self, user: User, session_id: str, now: float) -> IssuedTokens:
        session = self._sessions[session_id]
        refresh_token = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)
        self._refresh[_digest(refresh_token)] = _RefreshRecord(session_id, _digest(csrf_token))

        access_exp = min(now + self._settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60, session.expires_at)
        issued_at = datetime.fromtimestamp(now, tz=timezone.utc)
        expires_at = datetime.fromtimestamp(access_exp, tz=timezone.utc)
        access_token = encode_access_token(
            subject=user.email,
            session_id=session_id,
            jti=secrets.token_urlsafe(16),
            issued_at=issued_at,
            expires_at=expires_at,
        )
        return IssuedTokens(access_token, expires_at, refresh_token, csrf_token, session_id)

    # Refresh ----------------------------------------------------------------
    def rotate(self, refresh_token: Optional[str], csrf_token: Optional[str], load_user: Callable[[int], Optional[User]]) -> IssuedTokens:
        if not refresh_token:
            raise InvalidRefreshToken()
        now = self._clock()
        with self._lock:
            record = self._refresh.get(_digest(refresh_token))
            if record is None:
                raise InvalidRefreshToken()
            self._check_csrf(record, csrf_token)

            session = self._sessions.get(record.session_id)
            if session is None or session.revoked or session.expires_at <= now:
                self._drop_session(record.session_id)
                raise InvalidRefreshToken()

            if record.rotated_at is not None:
                if now - record.rotated_at > self._settings.REFRESH_REUSE_GRACE_SECONDS:
                    # Token já trocado reaparecendo: alguém tem uma cópia.
                    self._revoke_session(record.session_id)
                raise InvalidRefreshToken()

            user = load_user(session.user_id)
            if user is None:
                self._revoke_session(record.session_id)
                raise InvalidRefreshToken()

            record.rotated_at = now
            return self._issue(user, record.session_id, now)

    @staticmethod
    def _check_csrf(record: _RefreshRecord, csrf_token: Optional[str]) -> None:
        if not csrf_token or not hmac.compare_digest(_digest(csrf_token), record.csrf_hash):
            raise CsrfTokenMismatch()

    # Validação do access token ---------------------------------------------
    def validate_access(self, token: str) -> Optional[dict]:
        payload = decode_access_token(token)
        if payload is None:
            return None
        now = self._clock()
        with self._lock:
            if payload["jti"] in self._revoked_jti:
                return None
            session = self._sessions.get(payload["sid"])
            if session is None or session.revoked or session.expires_at <= now:
                return None
        return payload

    # Revogação --------------------------------------------------------------
    def revoke_access(self, payload: dict) -> None:
        """Revoga o access token apresentado e a sessão inteira dele."""
        with self._lock:
            self._revoked_jti[payload["jti"]] = float(payload["exp"])
            self._revoke_session(payload["sid"])

    def revoke_by_refresh(self, refresh_token: Optional[str], csrf_token: Optional[str]) -> bool:
        """Logout só com o cookie (access já vencido). Exige o CSRF da sessão."""
        if not refresh_token:
            return False
        with self._lock:
            record = self._refresh.get(_digest(refresh_token))
            if record is None:
                return False
            self._check_csrf(record, csrf_token)
            self._revoke_session(record.session_id)
            return True

    def _revoke_session(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session is not None:
            session.revoked = True
        for key in [k for k, r in self._refresh.items() if r.session_id == session_id]:
            del self._refresh[key]

    def _drop_session(self, session_id: str) -> None:
        self._revoke_session(session_id)
        self._sessions.pop(session_id, None)

    # Manutenção -------------------------------------------------------------
    def _prune(self, now: float) -> None:
        for sid in [s for s, data in self._sessions.items() if data.expires_at <= now]:
            self._drop_session(sid)
        for jti in [j for j, exp in self._revoked_jti.items() if exp <= now]:
            del self._revoked_jti[jti]

    def reset(self) -> None:
        with self._lock:
            self._sessions.clear()
            self._refresh.clear()
            self._revoked_jti.clear()
