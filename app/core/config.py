from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", extra="ignore")

    # Default timezone used for "today" logic
    TZ: str = "Asia/Kolkata"

    # Cache TTLs
    LIST_CACHE_TTL_SECONDS: int = 20
    DETAIL_CACHE_TTL_SECONDS: int = 20

    # HTTP
    FETCH_TIMEOUT_SECONDS: int = 12
    USER_AGENT: str = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )

settings = Settings()
