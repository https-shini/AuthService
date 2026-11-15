from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    # Endereço oficial (ex.: https://authservice.gcruz.dev.br). Com ele, quem
    # chega pelo endereço do Render é redirecionado para cá.
    PUBLIC_URL: str = ""
    # Definida pelo próprio Render (ex.: authservice-mbul.onrender.com).
    RENDER_EXTERNAL_HOSTNAME: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

settings = Settings()
