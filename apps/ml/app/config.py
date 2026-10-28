from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="SAASTA_ML_", extra="ignore")

    token: str = "dev-ml-token"  # noqa: S105 - refused at startup unless dev mode
    dev: bool = False
    # Fashion embedding model. Apache-2.0 open weights; swap for our fine-tuned checkpoint via EMBED_CHECKPOINT.
    embed_model: str = "hf-hub:Marqo/marqo-fashionSigLIP"
    embed_checkpoint: str | None = None
    # Try-on weights directory (FASHN VTON v1.5, Apache-2.0), downloaded by scripts/download_weights.sh
    tryon_weights: str = "./weights/tryon"
    tryon_steps: int = 30
    threads: int = 0  # 0 = torch default
    max_batch: int = 32


@lru_cache
def settings() -> Settings:
    return Settings()
