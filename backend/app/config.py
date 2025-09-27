from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Quant HTS Backend"
    debug: bool = True
    database_url: str
    kis_account_number: str | None = None
    kis_account_product_code: str | None = None
    kis_order_password: str | None = None
    kis_default_exchange: str = "KRX"
    kis_trade_environment: str = "vps"  # "vps" for mock, "prod" for live
    
    # LLM API 설정
    openai_api_key: str | None = None
    llm_model: str = "gpt-4"
    llm_temperature: float = 0.3
    llm_max_tokens: int = 1500

    class Config:
        env_file = ".env"


settings = Settings()
