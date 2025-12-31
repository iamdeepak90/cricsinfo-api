from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", extra="ignore")

    TZ: str = "Asia/Kolkata"

    LIST_CACHE_TTL_SECONDS: int = 15
    DETAIL_CACHE_TTL_SECONDS: int = 15

    FETCH_TIMEOUT_SECONDS: int = 10
    USER_AGENT: str = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )

    # performance controls
    MAX_LIVE_VERIFY: int = 8      # max match pages to fetch to verify LIVE
    MAX_UPCOMING: int = 10
    MAX_RESULTS: int = 10
    MAX_CONCURRENCY: int = 5

settings = Settings()
