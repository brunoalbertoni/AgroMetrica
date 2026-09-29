import tomllib
from functools import cached_property
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REGRAS_PATH = Path(__file__).with_name("regras.toml")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR.parent / ".env", BACKEND_DIR / ".env"), extra="ignore"
    )

    database_url: str = "mysql+pymysql://agro:agro@localhost:3307/agrometrica"
    jwt_secret: str = "troque-isto"
    jwt_expires_min: int = 480
    storage_dir: str = "../storage"
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def storage_path(self) -> Path:
        p = Path(self.storage_dir)
        return p if p.is_absolute() else (BACKEND_DIR / p).resolve()

    @cached_property
    def regras(self) -> dict:
        with REGRAS_PATH.open("rb") as f:
            return tomllib.load(f)


settings = Settings()
