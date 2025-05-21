from abc import ABC, abstractmethod
from typing import Any, Dict, List

from langchain_core.messages import BaseMessage

from travel_agent.core.llm.factory import LLMFactory


class AgentState:
    """에이전트의 상태를 관리하는 기본 클래스"""
    def __init__(self):
        self.messages: List[BaseMessage] = []
        self.context: Dict[str, Any] = {}
        self.metadata: Dict[str, Any] = {}


class BaseAgent(ABC):
    """모든 에이전트의 기본 클래스"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.state = AgentState()
        self.llm = LLMFactory.get_llm_with_fallback(name)
    
    @abstractmethod
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """에이전트의 주요 처리 로직"""
        pass
    
    @abstractmethod
    async def validate(self, input_data: Dict[str, Any]) -> bool:
        """입력 데이터 유효성 검증"""
        pass
    
    def update_state(self, **kwargs) -> None:
        """에이전트 상태 업데이트"""
        for key, value in kwargs.items():
            if hasattr(self.state, key):
                setattr(self.state, key, value)
    
    def get_state(self) -> AgentState:
        """현재 에이전트 상태 반환"""
        return self.state 