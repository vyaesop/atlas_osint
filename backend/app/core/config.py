"""Application configuration, loaded from environment / .env via pydantic-settings."""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import Field, PostgresDsn, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        # utf-8-sig tolerates a BOM, which PowerShell's `Out-File -Encoding utf8`
        # prepends — without it the first .env key is silently mis-read.
        env_file_encoding="utf-8-sig",
        case_sensitive=True,
        extra="ignore",
    )

    # ---- Application ----
    PROJECT_NAME: str = "Project Atlas"
    ENVIRONMENT: str = "development"
    API_V1_PREFIX: str = "/api/v1"
    BACKEND_CORS_ORIGINS: list[str] = Field(default_factory=list)

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def _split_cors(cls, v: Any) -> Any:
        # Allow a comma-separated string in addition to a JSON list.
        if isinstance(v, str) and not v.startswith("["):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # ---- Security ----
    SECRET_KEY: str = "change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    # ---- PostgreSQL ----
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "atlas"
    POSTGRES_PASSWORD: str = "atlas"
    POSTGRES_DB: str = "atlas"
    # Full async SQLAlchemy URL override. Set this to point at a managed/cloud
    # Postgres (e.g. RDS, Cloud SQL, Neon) without touching the discrete vars
    # above; it takes precedence when provided. Must use the asyncpg driver,
    # e.g. postgresql+asyncpg://user:pass@host:5432/db?ssl=require
    DATABASE_URL: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return str(
            PostgresDsn.build(
                scheme="postgresql+asyncpg",
                username=self.POSTGRES_USER,
                password=self.POSTGRES_PASSWORD,
                host=self.POSTGRES_HOST,
                port=self.POSTGRES_PORT,
                path=self.POSTGRES_DB,
            )
        )

    # ---- Neo4j ----
    # Set NEO4J_ENABLED=false for local dev without a graph DB: startup skips the
    # connection and graph projection no-ops (Postgres/SQLite stays source of truth).
    NEO4J_ENABLED: bool = True
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "neo4j"
    NEO4J_DATABASE: str = "neo4j"

    # ---- Redis ----
    REDIS_URL: str = "redis://localhost:6379/0"

    # ---- Scaling (Phase 6) ----
    # Cache expensive analytics/dashboard reads in Redis (version-invalidated).
    CACHE_ENABLED: bool = False
    CACHE_TTL_SECONDS: int = 300
    # Run graph-sync / search-index / ingestion off the request path via arq.
    # Default off → synchronous, in-request behavior (dev/local/tests).
    JOBS_ENABLED: bool = False
    # Safety cap on a single bulk import request.
    BULK_IMPORT_MAX_ITEMS: int = 50_000

    # ---- Search ----
    # "inmemory" (default; dev/tests) or "opensearch" (production).
    SEARCH_BACKEND: str = "inmemory"
    OPENSEARCH_URL: str = "http://opensearch:9200"
    OPENSEARCH_INDEX: str = "atlas-entities"
    # Embeddings power semantic search; the local provider needs no external svc.
    EMBEDDING_PROVIDER: str = "local"
    EMBEDDING_DIM: int = 256
    SEMANTIC_SEARCH_ENABLED: bool = True

    # ---- Analytics ----
    # "networkx" (default; computes locally over Postgres) or "neo4j_gds"
    # (future; offloads to Neo4j Graph Data Science for scale).
    ANALYTICS_BACKEND: str = "networkx"
    # Safety cap on how many nodes an on-demand analysis will load locally.
    ANALYTICS_MAX_NODES: int = 5000

    # ---- AI extraction (Phase 4) ----
    # "heuristic" (default; dependency-free, runs locally with no API key),
    # "gemini" (Google Gemini; requires GEMINI_API_KEY — has a free tier), or
    # "anthropic" (Claude; requires ANTHROPIC_API_KEY).
    AI_PROVIDER: str = "heuristic"
    ANTHROPIC_API_KEY: str | None = None
    AI_MODEL: str = "claude-opus-4-8"
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-2.0-flash"
    AI_MAX_OUTPUT_TOKENS: int = 4096
    # Cap on characters of document text sent to extraction in one pass.
    AI_MAX_INPUT_CHARS: int = 100_000

    # ---- Initial admin ----
    FIRST_ADMIN_EMAIL: str = "admin@atlas.example.com"
    FIRST_ADMIN_PASSWORD: str = "ChangeMe123!"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
