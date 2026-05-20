from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    host: str = "localhost"
    port: int = 8000
    database_url: str = "sqlite+aiosqlite:///./hitalent.db"


def get_settings():
    return Settings()
