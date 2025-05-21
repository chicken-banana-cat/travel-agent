from typing import Any, Dict, List, Optional
import json
from pydantic import BaseModel, Field, ValidationError

from langchain.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage

from .base import BaseAgent


class Activity(BaseModel):
    time: str
    activity: str
    location: str
    duration: str
    cost: int


class DayPlan(BaseModel):
    day: int
    activities: List[Activity]


class BudgetItem(BaseModel):
    estimated: float
    details: List[Dict[str, Any]] = Field(default_factory=list)


class Budget(BaseModel):
    transportation: BudgetItem
    accommodation: BudgetItem
    food: BudgetItem
    activities: BudgetItem
    total: float


class Recommendation(BaseModel):
    category: str
    items: List[str]


class TravelPlan(BaseModel):
    itinerary: List[DayPlan]
    budget: Budget
    recommendations: List[Recommendation]
    tips: List[str]


class PlannerResponse(BaseModel):
    status: str
    plan: Optional[TravelPlan] = None
    error: Optional[str] = None
    message: Optional[str] = None


class PlannerAgent(BaseAgent):
    """여행 계획 작성을 담당하는 에이전트"""
    
    def __init__(self):
        super().__init__(
            name="planner_agent",
            description="여행 일정 계획 작성을 담당하는 에이전트"
        )
        self.prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""당신은 여행 계획 전문가입니다.
            사용자의 선호도와 제약사항을 고려하여 최적의 여행 계획을 수립합니다.
            예산, 시간, 선호도 등을 종합적으로 고려하여 현실적인 계획을 제시하세요."""),
            HumanMessage(content="{requirements}")
        ])
    
    async def validate(self, input_data: Dict[str, Any]) -> bool:
        """계획 요구사항 유효성 검증"""
        required_fields = ["destination", "duration", "preferences"]
        return all(field in input_data for field in required_fields)
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:

        context = input_data.get("context") or input_data
        """계획 작성 처리"""
        if not await self.validate(context):
            return PlannerResponse(
                status="error",
                error="Invalid planning requirements",
                message="필수 요구사항(destination, duration, preferences)이 누락되었습니다."
            ).model_dump()
        
        try:

            # 1. LLM을 통한 계획 수립
            planning_prompt = ChatPromptTemplate.from_messages([
                SystemMessage(content="""당신은 여행 계획 전문가입니다.
                주어진 요구사항을 바탕으로 상세한 여행 계획을 수립해주세요.
                
                계획은 다음 요소들을 포함해야 합니다:
                1. 일별 상세 일정
                2. 예상 비용 (교통, 숙박, 식비, 관광 등)
                3. 추천 장소 및 활동
                4. 여행 팁 및 주의사항
                
                응답은 반드시 유효한 JSON 형식으로 제공해주세요.
                모든 숫자 값은 문자열이 아닌 실제 숫자로 제공해주세요.
                비용은 모두 원 단위로 제공해주세요.
                
                각 활동은 반드시 다음 필드를 포함해야 합니다:
                - time: 활동 시간
                - activity: 활동 설명
                - location: 장소
                - duration: 소요 시간
                - cost: 예상 비용
                
                예시:
                {
                    "itinerary": [
                        {
                            "day": 1,
                            "activities": [
                                {
                                    "time": "09:00",
                                    "activity": "활동 설명",
                                    "location": "장소",
                                    "duration": "소요 시간",
                                    "cost": 10000
                                }
                            ]
                        }
                    ],
                    "budget": {
                        "transportation": {
                            "estimated": 100000,
                            "details": [
                                {"item": "항공권", "cost": 50000},
                                {"item": "지하철", "cost": 50000}
                            ]
                        },
                        "accommodation": {
                            "estimated": 200000,
                            "details": [
                                {"item": "호텔 3박", "cost": 200000}
                            ]
                        },
                        "food": {
                            "estimated": 150000,
                            "details": [
                                {"item": "일일 식비", "cost": 150000}
                            ]
                        },
                        "activities": {
                            "estimated": 50000,
                            "details": [
                                {"item": "입장료", "cost": 50000}
                            ]
                        },
                        "total": 500000
                    },
                    "recommendations": [
                        {
                            "category": "카테고리",
                            "items": ["추천 항목"]
                        }
                    ],
                    "tips": ["여행 팁"]
                }"""),
                HumanMessage(content=f"""여행 계획을 수립해주세요:
                목적지: {context['destination']}
                기간: {context['duration']}
                선호사항: {context['preferences']}""")
            ])
            
            # LLM을 통한 계획 수립
            response = await self.llm.ainvoke(planning_prompt.format_messages())
            try:
                plan_data = json.loads(response.content)
                plan = TravelPlan.model_validate(plan_data)
            except (json.JSONDecodeError, ValidationError) as e:
                return PlannerResponse(
                    status="error",
                    error="Invalid plan format",
                    message=f"계획 데이터 형식이 올바르지 않습니다: {str(e)}"
                ).model_dump()
            
            # 2. 일정 최적화
            optimization_prompt = ChatPromptTemplate.from_messages([
                SystemMessage(content="""당신은 여행 일정 최적화 전문가입니다.
                주어진 여행 계획을 검토하고 최적화해주세요.
                
                다음 사항들을 고려하여 최적화해주세요:
                1. 이동 시간과 거리
                2. 관광지 운영 시간
                3. 식사 시간
                4. 휴식 시간
                5. 날씨와 계절
                
                응답은 반드시 유효한 JSON 형식으로 제공해주세요.
                기존 계획과 동일한 구조를 유지해주세요."""),
                HumanMessage(content=f"최적화할 계획: {plan.model_dump_json()}")
            ])
            
            # LLM을 통한 일정 최적화
            optimization_response = await self.llm.ainvoke(optimization_prompt.format_messages())
            try:
                optimized_data = json.loads(optimization_response.content)
                optimized_plan = TravelPlan.model_validate(optimized_data)
            except (json.JSONDecodeError, ValidationError) as e:
                return PlannerResponse(
                    status="error",
                    error="Invalid optimized plan format",
                    message=f"최적화된 계획 데이터 형식이 올바르지 않습니다: {str(e)}"
                ).model_dump()
            
            # 3. 예산 계획 수립
            budget_prompt = ChatPromptTemplate.from_messages([
                SystemMessage(content="""당신은 여행 예산 계획 전문가입니다.
                주어진 여행 계획을 바탕으로 상세한 예산 계획을 수립해주세요.
                
                다음 사항들을 고려하여 예산을 산출해주세요:
                1. 교통비 (항공/기차/버스/택시 등)
                2. 숙박비
                3. 식비
                4. 관광/활동 비용
                5. 기타 비용 (보험, 통신 등)
                
                응답은 반드시 유효한 JSON 형식으로 제공해주세요.
                모든 금액은 숫자로 제공해주세요.
                예시:
                {
                    "transportation": {"estimated": 100000, "details": []},
                    "accommodation": {"estimated": 200000, "details": []},
                    "food": {"estimated": 150000, "details": []},
                    "activities": {"estimated": 50000, "details": []},
                    "total": 500000
                }"""),
                HumanMessage(content=f"예산 계획 수립할 계획: {optimized_plan.model_dump_json()}")
            ])
            
            # LLM을 통한 예산 계획 수립
            budget_response = await self.llm.ainvoke(budget_prompt.format_messages())
            try:
                budget_data = json.loads(budget_response.content)
                budget_plan = Budget.model_validate(budget_data)
            except (json.JSONDecodeError, ValidationError) as e:
                return PlannerResponse(
                    status="error",
                    error="Invalid budget format",
                    message=f"예산 데이터 형식이 올바르지 않습니다: {str(e)}"
                ).model_dump()
            
            # 최종 계획 조합
            final_plan = TravelPlan(
                itinerary=optimized_plan.itinerary,
                budget=budget_plan,
                recommendations=optimized_plan.recommendations,
                tips=optimized_plan.tips
            )
            
            return PlannerResponse(
                status="success",
                plan=final_plan,
            ).model_dump()
            
        except Exception as e:
            return PlannerResponse(
                status="error",
                error="Planning failed",
                message=f"여행 계획 수립 중 오류가 발생했습니다: {str(e)}"
            ).model_dump() 