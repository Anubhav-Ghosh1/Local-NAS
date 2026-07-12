from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    SECRET_KEY: str = "CHANGE-THIS-SECRET-KEY-IN-PRODUCTION"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    FILES_ROOT: str = str(Path.home() / "storage" / "files")
    HOST: str = "0.0.0.0"
    PORT: int = 8080
    ALLOWED_ORIGINS: list[str] = ["*"]

    model_config = {"env_file": ".env"}


settings = Settings()
