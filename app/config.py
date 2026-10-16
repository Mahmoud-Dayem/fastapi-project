from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_secret_key: str
    ENV:str="development"

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
