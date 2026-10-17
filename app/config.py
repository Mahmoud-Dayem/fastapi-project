from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_secret_key: str
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    app_base_url: str = "http://localhost:8000"
    ENV:str="development"

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
