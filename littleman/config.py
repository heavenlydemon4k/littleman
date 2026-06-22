from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM
    llm_primary_model: str = "anthropic/claude-sonnet-4-6"
    llm_secondary_model: str = "anthropic/claude-haiku-4-5-20251001"
    anthropic_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"

    # Database
    database_url: str = "sqlite:///./littleman.db"

    # Workspace
    workspace_dir: Path = Path("./workspace")

    # Polymarket
    polymarket_api_key: str = ""
    polymarket_wallet_address: str = ""
    polymarket_private_key: str = ""

    # Web search (optional; Tavily-compatible). If unset, search degrades gracefully.
    search_api_key: str = ""
    search_endpoint: str = "https://api.tavily.com/search"

    # Budget / risk
    budget_usdc: float = 500.0
    max_position_pct: float = 0.20
    max_exposure_pct: float = 0.80
    max_session_drawdown_pct: float = 0.15
    max_total_drawdown_pct: float = 0.40
    max_category_exposure_pct: float = 0.40
    min_edge_pct: float = 0.03
    kelly_fraction: float = 0.25

    # Scheduler
    heartbeat_poll_interval_seconds: int = 30
    heartbeat_missed_threshold_minutes: int = 10
    idle_heartbeat_interval_hours: int = 4


settings = Settings()
