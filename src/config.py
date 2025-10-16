# config.py

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings
import os

from dotenv import load_dotenv
load_dotenv()

class Settings(BaseSettings):
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-5-nano", env="OPENAI_MODEL")
    vision_model: str = Field(default="gpt-4.1-mini", env="VISION_MODEL")
    
    zalo_bot_token: str = Field(..., env="ZALO_BOT_TOKEN")
    zalo_webhook_secret: str = Field(..., env="ZALO_WEBHOOK_SECRET")
    payment_public_webhook_url: str = Field(default="", env="PAYMENT_PUBLIC_WEBHOOK_URL")
    payment_webhook_bot_token: str = Field(default="", env="PAYMENT_WEBHOOK_BOT_TOKEN")
    greeting_override: str = Field(default="", env="GREETING_OVERRIDE")
    farewell_override: str = Field(default="", env="FAREWELL_OVERRIDE")
    
    database_url: str = Field(..., env="DATABASE_URL")
    db_host: str = Field(..., env="DB_HOST")
    db_port: int = Field(..., env="DB_PORT")
    db_name: str = Field(..., env="DB_NAME")
    db_user: str = Field(..., env="DB_USER")
    db_password: str = Field(..., env="DB_PASSWORD")


    redis_url: str = Field(..., env="REDIS_URL")
    ocr_api_key: str = Field(..., env="OCR_API_KEY")
    recipient_account: str = Field(default="13789999999", env="RECIPIENT_ACCOUNT")

    debug: bool = Field(default=False, env="DEBUG")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    environment: str = Field(default="development", env="ENVIRONMENT")

    # << THAY ĐỔI: Xóa Supabase, thêm Qdrant >>
    qdrant_url: str = Field(..., env="QDRANT_URL")
    qdrant_api_key: str = Field(..., env="QDRANT_API_KEY")
    qdrant_collection_name: str = Field(default="recall_memories", env="QDRANT_COLLECTION_NAME")
    
    chat_history_limit: int = Field(default=5, env="CHAT_HISTORY_LIMIT")
    max_products_display: int = Field(default=6, env="MAX_PRODUCTS_DISPLAY")
    retry_attempts: int = Field(default=2, env="RETRY_ATTEMPTS")
    quick_response_enabled: bool = Field(default=True, env="QUICK_RESPONSE_ENABLED")
    keyword_routing_enabled: bool = Field(default=True, env="KEYWORD_ROUTING_ENABLED")
    
    scheduler_enabled: bool = Field(default=True, env="SCHEDULER_ENABLED")
    scheduler_dev_mode: bool = Field(default=False, env="SCHEDULER_DEV_MODE")
    followup_check_interval_hours: int = Field(default=24, env="FOLLOWUP_CHECK_INTERVAL_HOURS")
    followup_check_interval_minutes: int = Field(default=5, env="FOLLOWUP_CHECK_INTERVAL_MINUTES")
    followup_days_threshold: int = Field(default=30, env="FOLLOWUP_DAYS_THRESHOLD")
    followup_minutes_threshold: int = Field(default=2, env="FOLLOWUP_MINUTES_THRESHOLD")

    sepay_api_key: str = Field(default="", env="SEPAY_API_KEY")
    
    payment_bank_account: str = Field(default="0395695023", env="PAYMENT_BANK_ACCOUNT")
    payment_bank_name: str = Field(default="VPBank", env="PAYMENT_BANK_NAME")
    payment_code_prefix: str = Field(default="TKPS2E", env="PAYMENT_CODE_PREFIX")

    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        case_sensitive = False
        env_file_encoding = 'utf-8'

settings = Settings()
DATABASE_URL = settings.database_url