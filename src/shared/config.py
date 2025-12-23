"""Configuration management for Databricks Docs MCP."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    # Paths
    data_dir: Path = Path("./data")
    chroma_path: Path = Path("./data/chroma")
    sections_index_path: Path = Path("./data/sections_index.json")
    crawl_state_path: Path = Path("./data/crawl_state.json")

    # Crawler settings
    rate_limit: float = 1.0  # requests per second
    max_concurrent: int = 5
    max_chunk_tokens: int = 1000
    chunk_overlap_tokens: int = 100

    # Embedding model
    embedding_model: str = "all-MiniLM-L6-v2"

    # Documentation source
    base_url: str = "https://docs.databricks.com"
    sitemap_url: str = "https://docs.databricks.com/aws/en/sitemap.xml"
    cloud_region: str = "aws"
    language: str = "en"

    model_config = {
        "env_file": ".env",
        "env_prefix": "DATABRICKS_DOCS_",
    }


settings = Settings()
