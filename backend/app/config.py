"""Application settings, read from environment variables or the root .env file."""
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]  # repository root


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: str = ""
    # Claude models: Sonnet for reasoning-heavy agents, Haiku for cheap structuring steps
    model_reasoning: str = "anthropic/claude-sonnet-5-5"
    model_fast: str = "anthropic/claude-haiku-5-5"

    database_url: str = f"sqlite:///{(ROOT / 'data' / 'taxpulse.db').as_posix()}"
    upload_dir: Path = ROOT / "data" / "uploads"
    demo_dir: Path = ROOT / "data" / "demo"

    # USD per million tokens (input, output), from platform.claude.com/docs/en/about-claude/pricing
    prices_per_mtok: dict[str, tuple[float, float]] = {
        "claude-sonnet-5-5": (2.0, 10.0),
        "claude-haiku-5-5": (0.10, 0.50),
    }

    max_upload_mb: int = 20
    bmf_feed_url: str = "https://www.bundesfinanzministerium.de/SiteGlobals/Functions/RSSFeed/DE/Steuern/RSSSteuern.xml"
    bfh_feeds: dict[str, str] = {  # Federal Fiscal Court: feed URL -> kind of publication
        "https://www.bundesfinanzhof.de/de/precedent.rss": "bfh_ruling",
        "https://www.bundesfinanzhof.de/de/news.rss": "press_release",
    }
    bfh_max_age_days: int = 60  # first fetch: skip older items so the agents are not flooded
    # The "Send to TaxPulse" browser button may post feeds from these sites only.
    feed_sender_origins: list[str] = ["https://www.bundesfinanzministerium.de", "https://bundesfinanzministerium.de"]
    alert_threshold: int = 60
    demo_mode: bool = False  # public demo: agents replay recorded results, no API key, no uploads
    demo_idle_reset_minutes: int = 45  # the shared demo starts fresh after this much quiet
    static_dir: Path | None = None  # built frontend to serve (one container for the public demo)
    scheduler: bool = True  # background loop for the weekly check; switched off in tests
    frontend_origin: str = "http://localhost:5173"

    @field_validator("anthropic_api_key", mode="before")
    @classmethod
    def _clean_key(cls, v):
        # Tolerate spaces and quotes pasted around the key in .env
        return str(v or "").strip().strip('"').strip("'").strip()

    @property
    def llm_configured(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def key_problem(self) -> str | None:
        """Obvious paste mistakes, detected without calling the API."""
        k = self.anthropic_api_key
        if not k:
            return None
        if not k.startswith("sk-ant-"):
            return "The API key in .env should start with sk-ant-."
        if k.count("sk-ant-") > 1:
            return "The API key in .env seems to be pasted twice. Keep a single key."
        if any(c.isspace() for c in k):
            return "The API key in .env contains spaces or line breaks."
        return None


settings = Settings()
