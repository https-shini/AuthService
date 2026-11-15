"""Configuração da aplicação, lida do ambiente ou de um arquivo `.env`.

A aplicação NÃO inicia sem uma SECRET_KEY segura: ausente, curta, igual a
um texto de exemplo ou igual a uma chave que já foi publicada no
repositório. Os valores nunca aparecem nas mensagens de erro nem nos logs
(`hide_input_in_errors`).
"""

import hashlib

from pydantic import ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MIN_SECRET_KEY_LENGTH = 32

# SHA-256 de chaves que já ficaram públicas neste repositório: a do antigo
# `.env.example` e a de um `.env` commitado por engano no histórico. Só os
# hashes ficam aqui, para não republicar os valores.
_PUBLISHED_SECRET_KEY_HASHES = frozenset(
    {
        "efe1ad3cb08c4371a4a92023ed14b6d3e7d01497e65f12cc0d34d22c0035e375",
        "1a04b567c76dc090eaf3b49c5992cecc27558eeaf1835165ee258c138e9ecc1a",
    }
)

_PLACEHOLDER_MARKERS = ("troque", "change", "sua-chave", "your-secret", "secret-key", "exemplo")

_ALLOWED_ALGORITHMS = {"HS256", "HS384", "HS512"}

SECRET_KEY_HELP = (
    'Gere uma chave com: python -c "import secrets; print(secrets.token_urlsafe(48))" '
    "e defina-a na variável de ambiente SECRET_KEY (ou no arquivo .env)."
)


class Settings(BaseSettings):
    # --- JWT ---------------------------------------------------------------
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    # Duração máxima de uma sessão (refresh token), contada a partir do login.
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 480
    # Janela em que reapresentar um refresh token já trocado é tratado como
    # corrida entre abas (401 sem revogar) e não como roubo (revoga a sessão).
    REFRESH_REUSE_GRACE_SECONDS: int = 10

    # --- Cookies ------------------------------------------------------------
    # True em produção (HTTPS). Navegadores aceitam cookies Secure em
    # http://localhost; só desative para testar por HTTP em outro host.
    COOKIE_SECURE: bool = True

    # --- Rate limiting do /token -----------------------------------------
    LOGIN_IP_MAX_ATTEMPTS: int = 20
    LOGIN_IP_WINDOW_SECONDS: int = 60
    LOGIN_ACCOUNT_IP_MAX_FAILURES: int = 5
    LOGIN_ACCOUNT_MAX_FAILURES: int = 20
    LOGIN_FAILURE_WINDOW_SECONDS: int = 900
    LOGIN_LOCKOUT_SECONDS: int = 900

    # --- Rede / HTTPS -------------------------------------------------------
    # Quantos proxies reversos confiáveis ficam na frente da aplicação.
    # 0 = usa o IP da conexão e ignora X-Forwarded-For (não falsificável).
    # No Render (um proxy), use 1.
    TRUSTED_PROXY_HOPS: int = 0
    # Só ligue com HTTPS realmente configurado; o header só é enviado em
    # requisições HTTPS.
    HSTS_ENABLED: bool = False
    HSTS_MAX_AGE: int = 31_536_000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        hide_input_in_errors=True,
    )

    @field_validator("SECRET_KEY")
    @classmethod
    def _validate_secret_key(cls, value: str) -> str:
        key = value.strip()
        if not key:
            raise ValueError(f"SECRET_KEY não definida. {SECRET_KEY_HELP}")
        if len(key) < MIN_SECRET_KEY_LENGTH:
            raise ValueError(
                f"SECRET_KEY muito curta (mínimo de {MIN_SECRET_KEY_LENGTH} caracteres). {SECRET_KEY_HELP}"
            )
        if hashlib.sha256(key.encode("utf-8")).hexdigest() in _PUBLISHED_SECRET_KEY_HASHES:
            raise ValueError(
                "SECRET_KEY é uma chave já publicada no repositório e não pode ser usada. "
                + SECRET_KEY_HELP
            )
        lowered = key.lower()
        if any(marker in lowered for marker in _PLACEHOLDER_MARKERS) or len(set(key)) < 8:
            raise ValueError(f"SECRET_KEY parece um valor de exemplo ou previsível. {SECRET_KEY_HELP}")
        return key

    @field_validator("ALGORITHM")
    @classmethod
    def _validate_algorithm(cls, value: str) -> str:
        algorithm = value.strip().upper()
        if algorithm not in _ALLOWED_ALGORITHMS:
            raise ValueError(f"ALGORITHM deve ser um de {sorted(_ALLOWED_ALGORITHMS)}.")
        return algorithm

    @model_validator(mode="after")
    def _validate_ranges(self) -> "Settings":
        positives = {
            "ACCESS_TOKEN_EXPIRE_MINUTES": self.ACCESS_TOKEN_EXPIRE_MINUTES,
            "REFRESH_TOKEN_EXPIRE_MINUTES": self.REFRESH_TOKEN_EXPIRE_MINUTES,
            "LOGIN_IP_MAX_ATTEMPTS": self.LOGIN_IP_MAX_ATTEMPTS,
            "LOGIN_IP_WINDOW_SECONDS": self.LOGIN_IP_WINDOW_SECONDS,
            "LOGIN_ACCOUNT_IP_MAX_FAILURES": self.LOGIN_ACCOUNT_IP_MAX_FAILURES,
            "LOGIN_ACCOUNT_MAX_FAILURES": self.LOGIN_ACCOUNT_MAX_FAILURES,
            "LOGIN_FAILURE_WINDOW_SECONDS": self.LOGIN_FAILURE_WINDOW_SECONDS,
            "LOGIN_LOCKOUT_SECONDS": self.LOGIN_LOCKOUT_SECONDS,
        }
        for name, value in positives.items():
            if value <= 0:
                raise ValueError(f"{name} deve ser maior que zero.")
        if self.REFRESH_TOKEN_EXPIRE_MINUTES < self.ACCESS_TOKEN_EXPIRE_MINUTES:
            raise ValueError("REFRESH_TOKEN_EXPIRE_MINUTES não pode ser menor que ACCESS_TOKEN_EXPIRE_MINUTES.")
        if self.TRUSTED_PROXY_HOPS < 0 or self.REFRESH_REUSE_GRACE_SECONDS < 0:
            raise ValueError("TRUSTED_PROXY_HOPS e REFRESH_REUSE_GRACE_SECONDS não podem ser negativos.")
        return self


def describe_settings_error(error: ValidationError) -> str:
    """Mensagem legível com os campos inválidos, sem expor valores."""
    lines = []
    for issue in error.errors():
        field = ".".join(str(part) for part in issue.get("loc", ())) or "configuração"
        message = str(issue.get("msg", "valor inválido")).removeprefix("Value error, ")
        lines.append(f"  - {field}: {message}")
    return "Configuração inválida; a aplicação não foi iniciada:\n" + "\n".join(lines)


def load_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as error:
        raise RuntimeError(describe_settings_error(error)) from None


settings = load_settings()
