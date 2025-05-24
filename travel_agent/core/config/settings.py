import os
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

# Load environment variables from .env file
PROJECT_ROOT = Path.cwd()
env_path = PROJECT_ROOT.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    print(f"Warning: .env file not found at {env_path}")


class ModelConfig(BaseModel):
    """개별 모델 설정"""

    name: str
    provider: str  # openai, anthropic, etc.
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    streaming: bool = True


class AgentConfig(BaseModel):
    """에이전트별 모델 설정"""

    primary_model: str  # 기본 모델 이름
    fallback_models: List[str] = []  # 대체 모델 목록
    max_retries: int = 3


class Settings(BaseSettings):
    """전체 애플리케이션 설정"""

    # API 키 설정
    OPENAI_API_KEY: str
    anthropic_api_key: Optional[str] = None
    NAVER_CLIENT_ID: str
    NAVER_CLIENT_SECRET: str
    SMTP_SERVER: str
    SMTP_PORT: int
    SMTP_USERNAME: str
    SMTP_PASSWORD: str
    SENDER_EMAIL: str
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_REGION: str
    AWS_SQS_URL: str
    # 기본 모델 설정
    MODEL_NAME: str
    AWS_ACCOUNT_ID: str

    # 모델 설정
    models: Dict[str, ModelConfig] = Field(
        default_factory=lambda: {
            "gpt-4.1-mini-2025-04-14": ModelConfig(
                name="gpt-4.1-mini-2025-04-14", provider="openai", temperature=0.7
            ),
            "claude-3-opus": ModelConfig(
                name="claude-3-opus", provider="anthropic", temperature=0.7
            ),
        }
    )

    # 에이전트별 설정
    agent_configs: Dict[str, AgentConfig] = Field(
        default_factory=lambda: {
            "orchestrator": AgentConfig(
                primary_model="gpt-4.1-mini-2025-04-14", fallback_models=["gpt-4"]
            ),
            "search_agent": AgentConfig(
                primary_model="gpt-4.1-mini-2025-04-14", fallback_models=[]
            ),
            "planner_agent": AgentConfig(
                primary_model="gpt-4.1-mini-2025-04-14", fallback_models=["gpt-4"]
            ),
            "calendar_agent": AgentConfig(
                primary_model="gpt-4.1-mini-2025-04-14", fallback_models=[]
            ),
            "mail_agent": AgentConfig(
                primary_model="gpt-4.1-mini-2025-04-14", fallback_models=[]
            ),
        }
    )

    class Config:
        env_file = str(env_path)
        env_file_encoding = "utf-8"
        env_prefix = ""
        case_sensitive = True


# 디버그: 환경 변수 로딩 확인
print("Current working directory:", os.getcwd())
print("Environment variables:")
print("OPENAI_API_KEY:", os.getenv("OPENAI_API_KEY"))
print("MODEL_NAME:", os.getenv("MODEL_NAME"))
print("ENV file path:", env_path)
print("ENV file exists:", env_path.exists())

try:
    settings = Settings()
    print("Settings loaded successfully!")
except Exception as e:
    print(f"Error loading settings: {e}")
