
from langchain_community.chat_models import ChatAnthropic
from langchain_core.language_models import BaseLanguageModel
from langchain_openai import ChatOpenAI

from travel_agent.core.config.settings import settings


class LLMFactory:
    """LLM 모델 생성을 관리하는 팩토리 클래스"""
    
    _providers = {
        "openai": ChatOpenAI,
        "anthropic": ChatAnthropic
    }
    
    @classmethod
    def create_llm(cls, model_name: str) -> BaseLanguageModel:
        """모델 이름에 따라 LLM 인스턴스 생성"""
        if model_name not in settings.models:
            raise ValueError(f"Unknown model: {model_name}")
        
        model_config = settings.models[model_name]
        provider_class = cls._providers.get(model_config.provider)
        
        if not provider_class:
            raise ValueError(f"Unknown provider: {model_config.provider}")
        
        # 공통 설정
        kwargs = {
            "model_name": model_config.name,
            "temperature": model_config.temperature,
            "streaming": model_config.streaming
        }
        
        # provider별 추가 설정
        if model_config.provider == "openai":
            kwargs["openai_api_key"] = settings.OPENAI_API_KEY
        elif model_config.provider == "anthropic":
            kwargs["anthropic_api_key"] = settings.anthropic_api_key
        
        if model_config.max_tokens:
            kwargs["max_tokens"] = model_config.max_tokens
        
        return provider_class(**kwargs)
    
    @classmethod
    def get_llm_with_fallback(cls, agent_name: str) -> BaseLanguageModel:
        """에이전트에 대한 LLM 생성 (fallback 포함)"""
        if agent_name not in settings.agent_configs:
            raise ValueError(f"Unknown agent: {agent_name}")
        
        agent_config = settings.agent_configs[agent_name]
        
        # 기본 모델 시도
        try:
            return cls.create_llm(agent_config.primary_model)
        except Exception as e:
            # fallback 모델 시도
            for fallback_model in agent_config.fallback_models:
                try:
                    return cls.create_llm(fallback_model)
                except Exception:
                    continue
            
            # 모든 모델 실패 시 예외 발생
            raise Exception(f"Failed to create LLM for agent {agent_name}: {str(e)}") 