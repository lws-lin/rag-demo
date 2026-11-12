from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://rag:rag@localhost:5432/rag"
    jwt_secret: str = "dev-only-change-me"
    jwt_expire_minutes: int = 720
    admin_username: str = "admin"
    admin_password: str = "ChangeMe-123456"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    inbox_dir: str = ""
    library_dir: str = ""
    chunk_size: int = 800
    chunk_overlap: int = 120
    max_upload_bytes: int = 20 * 1024 * 1024
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    embedding_dim: int = 512
    embedding_cache_dir: str = ""
    chat_base_url: str = ""
    chat_api_key: str = ""
    chat_model: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def inbox_path(self) -> Path:
        if self.inbox_dir:
            return Path(self.inbox_dir)
        return REPO_ROOT / "data" / "inbox"

    @property
    def library_path(self) -> Path:
        if self.library_dir:
            return Path(self.library_dir)
        return REPO_ROOT / "data" / "library"

    @property
    def embedding_cache_path(self) -> Path:
        if self.embedding_cache_dir:
            return Path(self.embedding_cache_dir)
        return REPO_ROOT / "data" / "models"


settings = Settings()
