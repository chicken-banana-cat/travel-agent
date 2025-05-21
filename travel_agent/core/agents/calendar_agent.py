from typing import Any, Dict, List

from langchain.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage

from .base import BaseAgent


class CalendarAgent(BaseAgent):
    """캘린더 관리를 담당하는 에이전트"""
    
    def __init__(self):
        super().__init__(
            name="calendar_agent",
            description="여행 일정의 캘린더 관리를 담당하는 에이전트"
        )
        self.prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""당신은 캘린더 관리 전문가입니다.
            여행 일정을 캘린더에 등록하고 관리합니다.
            일정 충돌을 방지하고 효율적인 시간 관리를 도와주세요."""),
            HumanMessage(content="{action}")
        ])
    
    async def validate(self, input_data: Dict[str, Any]) -> bool:
        """캘린더 작업 유효성 검증"""
        required_fields = ["action", "event"]
        return all(field in input_data for field in required_fields)
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """캘린더 작업 처리"""
        if not await self.validate(input_data):
            return {
                "status": "error",
                "error": "Invalid calendar operation",
                "message": "필수 요구사항(action, event)이 누락되었습니다."
            }
        
        action = input_data["action"]
        event = input_data["event"]
        
        # 실제 캘린더 작업 로직 구현
        # 1. 캘린더 API 연동 (Google Calendar 등)
        # 2. 일정 CRUD 작업 수행
        # 3. 결과 반환
        
        return {
            "status": "success",
            "operation": action,
            "event": event
        } 