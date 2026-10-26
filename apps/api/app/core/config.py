from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="SAASTA_", extra="ignore")

    env: Literal["dev", "test", "prod"] = "dev"
    app_name: str = "Saasta"
    public_web_url: str = "http://localhost:3000"
    public_api_url: str = "http://localhost:8000"

    # Secrets. In prod these must be set; see validate_prod().
    secret_key: str = Field(default="dev-only-change-me-dev-only-change-me", min_length=32)
    ip_hash_salt: str = "dev-salt"

    database_url: str = "sqlite+aiosqlite:///./data/saasta.db"
    redis_url: str | None = None

    cors_origins: list[str] = ["http://localhost:3000"]
    trusted_proxy_hops: int = 0

    # Upload limits
    max_image_bytes: int = 10 * 1024 * 1024
    max_video_bytes: int = 60 * 1024 * 1024
    max_video_seconds: int = 90
    max_image_pixels: int = 40_000_000
    upload_dir: str = "./data/uploads"

    # Providers (all optional; pipeline skips missing ones)
    serpapi_key: str | None = None
    apify_token: str | None = None
    fashn_api_key: str | None = None
    default_country: str = "pk"
    default_currency: str = "PKR"

    # Rate limits (requests per window)
    rl_search_per_min: int = 10
    rl_search_per_day: int = 200
    rl_auth_per_min: int = 5
    rl_tryon_per_day: int = 10

    access_token_minutes: int = 60 * 24 * 7
    search_ttl_hours: int = 72

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def is_prod(self) -> bool:
        return self.env == "prod"

    def validate_prod(self) -> None:
        if not self.is_prod:
            return
        problems = []
        if self.secret_key.startswith("dev-only"):
            problems.append("SAASTA_SECRET_KEY must be set")
        if self.ip_hash_salt == "dev-salt":
            problems.append("SAASTA_IP_HASH_SALT must be set")
        if self.database_url.startswith("sqlite"):
            problems.append("use Postgres in prod")
        if any(o == "*" for o in self.cors_origins):
            problems.append("wildcard CORS not allowed in prod")
        if not self.redis_url:
            problems.append("SAASTA_REDIS_URL required in prod (rate limiting)")
        if problems:
            raise RuntimeError("Bad production config: " + "; ".join(problems))


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.validate_prod()
    return s
