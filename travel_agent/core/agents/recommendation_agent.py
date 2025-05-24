from typing import Dict, Any, List, Iterable
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from ..config.settings import settings
from ...utils import update_dict
import json

from ...utils.cache_client import cache_client


class RecommendationAgent:
    """여행 추천을 위한 대화형 에이전트"""

    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.MODEL_NAME,
            temperature=0.7
        )
        
        # 추천 단계 정의
        self.recommendation_steps = {
            "preferences": {
                "prompt": """당신은 여행 추천 전문가입니다. 사용자의 여행 선호도를 파악하기 위해 대화를 이어가세요.
                
                현재까지 파악된 정보:
                {current_context}
                {additional_context}
                
                이미 수집된 정보는 다시 물어보지 마세요. 아직 수집되지 않은 정보만 물어보세요.
                다음 항목들 중 아직 파악되지 않은 항목만 순차적으로 파악해주세요:
                1. 여행 스타일 (휴양/관광/문화/액티비티 등)
                2. 선호하는 활동 (해변/등산/맛집/쇼핑 등)
                3. 예산 범위
                4. 선호하는 숙박 유형 (호텔/게스트하우스/리조트 등)
                5. 교통수단 선호도 (렌터카/대중교통 등)
                
                사용자의 응답에서 활동이나 선호도를 명확하게 파악했다면, 해당 정보를 collected_info에 반드시 포함시켜주세요.
                
                각 항목에 대해 구체적인 예시를 들어 설명하고, 사용자의 답변을 바탕으로 다음 단계로 진행하세요.
                
                응답은 다음 JSON 형식으로만 제공하세요:
                {{
                    "status": "success",
                    "message": "사용자에게 보여줄 메시지",
                    "current_step": "preferences",
                    "collected_info": {{
                        "travel_style": "파악된 여행 스타일",
                        "activities": ["선호 활동들"],
                        "budget": "예산 범위",
                        "accommodation": "숙박 선호도",
                        "transportation": "교통수단 선호도"
                    }},
                }}""",
                "required_fields": ["travel_style", "activities", "budget", "accommodation", "transportation"]
            },
            "destination": {
                "prompt": """사용자의 선호도를 바탕으로 여행지를 추천해주세요. 그리고 사용자에게 갈 여행지를 물어보세요.
                
                사용자 선호도:
                {preferences}
                
                다음 사항을 고려하여 추천해주세요:
                1. 여행 스타일에 맞는 장소
                2. 선호하는 활동을 즐길 수 있는 곳
                3. 예산 범위 내에서 가능한 곳
                4. 선호하는 숙박 시설이 있는 곳
                5. 교통수단 선호도에 맞는 곳
                
                응답은 다음 JSON 형식으로만 제공하세요:
                {{
                    "status": "success",
                    "message": "추천 메시지",
                    "current_step": "destination",
                    "recommendations": [
                        {{
                            "name": "추천 장소",
                            "reason": "추천 이유",
                            "best_time": "최적 여행 시기",
                            "estimated_budget": "예상 비용",
                            "highlights": ["주요 특징들"]
                        }}
                    ],
                }}""",
                "required_fields": ["recommendations"]
            }
        }

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """메시지 처리 및 추천 단계 진행"""
        message = input_data.get("message", "")
        current_step = "preferences"
        session_id = input_data["session_id"]
        session_data = cache_client.get_conversation_history(session_id)
        previous_collected_info = session_data.get("collected_info", [])
        if previous_collected_info and  isinstance(previous_collected_info, Iterable):
            before_collected_info = previous_collected_info[-1]["data"] or {}
        else:
            before_collected_info = {}

        if step := before_collected_info.get("next_step"):
            current_step = step

        # 현재 단계의 프롬프트 가져오기
        step_config = self.recommendation_steps[current_step]
        context = json.dumps(before_collected_info, ensure_ascii=False, indent=2)


        before_contexts = session_data.get("context", [])
        if before_contexts:
            additional_context = before_contexts[-1].get("data", {})
        else:
            additional_context = {}
        # 컨텍스트에 따라 프롬프트 포맷팅
        if current_step == "preferences":
            prompt_content = step_config["prompt"].format(current_context=context, additional_context=additional_context)
            formatted_prompt = [
                SystemMessage(content=prompt_content),
                HumanMessage(content=message)
            ]
        else:  # destination 단계
            prompt_content = step_config["prompt"].format(preferences=context, additional_context=additional_context)
            formatted_prompt = [
                SystemMessage(content=prompt_content),
                HumanMessage(content=message)
            ]

        # LLM 호출
        response = await self.llm.ainvoke(formatted_prompt)
        
        try:
            # 응답이 JSON 형식인지 확인
            content = response.content.strip()
            print(f"LLM Response: {content}")  # 디버깅을 위한 로그 추가
            
            if not content.startswith('{') or not content.endswith('}'):
                print(f"Invalid JSON format. Content: {content}")  # 디버깅을 위한 로그 추가
                return {
                    "status": "error",
                    "message": "LLM 응답이 JSON 형식이 아닙니다",
                    "raw_response": content,
                    "current_step": current_step
                }
            
            result = json.loads(content)
            
            # 다음 단계 결정
            if current_step == "preferences":
                # 모든 필수 정보가 수집되었는지 확인
                collected_info = update_dict(before_collected_info, result.get("collected_info", {}))
                missing_fields = [
                    field for field in step_config["required_fields"]
                    if not collected_info.get(field)
                ]
                if not missing_fields:
                    collected_info["next_step"] = "destination"
                else:
                    collected_info["next_step"] = "preferences"
                cache_client.add_message(session_id, {
                    "type": "collected_info",
                    "data": collected_info
                })

            
            return result
            
        except Exception as e:
            raise e
            return {
                "status": "error",
                "message": f"추천 처리 중 오류가 발생했습니다: {str(e)}",
                "current_step": current_step
            } 