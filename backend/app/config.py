from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Quant HTS Backend"
    debug: bool = True

    class Config:
        env_file = ".env"


settings = Settings()
