from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_env: str = "development"
    secret_key: str
    admin_email: str
    admin_password: str
    database_url: str = "sqlite:///./mera_music_ai.db"
    access_token_minutes: int = 60
    acestep_base_url: str = ""
    payment_provider: str = ""
    payment_webhook_secret: str = ""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
