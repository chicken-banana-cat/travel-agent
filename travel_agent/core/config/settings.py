from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

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
    MODEL_NAME: str
    AWS_ACCOUNT_ID: str
    GOOGLE_CLIENT_ID: str
    GOOGLE_PRIVATE_KEY_ID: str
    GOOGLE_PRIVATE_KEY: str

    # 모델 설정
    models: Dict[str, ModelConfig] = Field(
        default_factory=lambda: {
            "gpt-4.1-mini": ModelConfig(
                name="gpt-4.1-mini", provider="openai", temperature=0.7
            ),
            "claude-3-opus": ModelConfig(
                name="claude-3-opus", provider="anthropic", temperature=0.7
            ),
            # TODO 사용할 모델 설정 추가
        }
    )

    # 에이전트별 설정
    agent_configs: Dict[str, AgentConfig] = Field(
        default_factory=lambda: {
            "orchestrator": AgentConfig(
                primary_model="gpt-4.1-mini", fallback_models=["gpt-4"]
            ),
            "search_agent": AgentConfig(
                primary_model="gpt-4.1-mini", fallback_models=[]
            ),
            "planner_agent": AgentConfig(
                primary_model="gpt-4.1-mini", fallback_models=["gpt-4"]
            ),
            "calendar_agent": AgentConfig(
                primary_model="gpt-4.1-mini", fallback_models=[]
            ),
            "mail_agent": AgentConfig(primary_model="gpt-4.1-mini", fallback_models=[]),
        }
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # MODEL_NAME을 사용하여 모든 에이전트의 primary_model 업데이트
        for agent_config in self.agent_configs.values():
            agent_config.primary_model = self.MODEL_NAME

    class Config:
        env_file = str(env_path)
        env_file_encoding = "utf-8"
        env_prefix = ""
        case_sensitive = True


try:
    settings = Settings()
    print("Settings loaded successfully!")
except Exception as e:
    print(f"Error loading settings: {e}")
