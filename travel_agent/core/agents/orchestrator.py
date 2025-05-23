from typing import Any, Dict, List, Optional, TypedDict, AsyncGenerator
import json
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.pregel import Pregel

from .search_agent import SearchAgent
from .planner_agent import PlannerAgent
from .calendar_agent import CalendarAgent
from .mail_agent import MailAgent
from .recommendation_agent import RecommendationAgent
from ..config.settings import settings
from ...tasks import process_search_and_mail
from ...utils import update_dict
from ...utils.cache_client import cache_client


class AgentState(TypedDict):
    """에이전트 상태를 정의하는 타입"""
    messages: List[BaseMessage]
    current_agent: Optional[str]
    context: Dict[str, Any]
    result: Optional[Dict[str, Any]]
    workflow_history: List[Dict[str, Any]]
    next_steps: List[str]
    session_id: str


class Orchestrator:
    """LangGraph를 사용한 에이전트 조율 시스템"""

    def __init__(self):
        self.agents = {
            "search": SearchAgent(),
            "planner": PlannerAgent(),
            "calendar": CalendarAgent(),
            "mail": MailAgent(),
            "recommendation": RecommendationAgent()
        }

        # LLM 초기화
        self.llm = ChatOpenAI(
            model=settings.MODEL_NAME,
            temperature=0
        )

        # 워크플로우 그래프 초기화
        self.workflow = self._create_workflow()

    def _get_next_node(self, state: AgentState) -> str:
        """다음 실행할 노드를 결정하는 함수
        
        Args:
            state: 현재 워크플로우 상태
            
        Returns:
            str: 다음 실행할 노드의 이름
        """
        # need_more_info 상태인 경우 determine_next_steps로 라우팅
        if (
                state.get("result") is not None and
                state.get("result", {}).get("status") == "need_more_info"
        ):
            return "determine_next_steps"

        # current_agent가 있는 경우 해당 에이전트로 라우팅
        if state.get("current_agent"):
            return state["current_agent"]

        # 기본값으로 search 에이전트로 라우팅
        return "determine_next_steps"

    def _get_next_step_node(self, state: AgentState) -> str:
        """다음 단계의 노드를 결정하는 함수
        
        Args:
            state: 현재 워크플로우 상태
            
        Returns:
            str: 다음 실행할 노드의 이름
        """
        # next_steps가 없으면 워크플로우 종료
        if not state["next_steps"]:
            return "end"

        # 다음 단계 가져오기
        next_step = state["next_steps"][0]
        state["next_steps"] = state["next_steps"][1:]

        # 다음 단계에 따라 적절한 에이전트 선택
        if next_step in ["search", "planner", "calendar", "mail", "recommendation"]:
            state["current_agent"] = next_step
            return next_step
        else:
            state["current_agent"] = "analyze_intent"
            return "analyze_intent"

    def _create_workflow(self) -> Pregel:
        """LangGraph 워크플로우 생성"""
        # 초기 상태 정의
        initial_state = {
            "messages": [],
            "current_agent": None,
            "context": {},
            "result": None,
            "workflow_history": [],
            "next_steps": []
        }

        # 그래프 생성
        workflow = StateGraph(AgentState)

        # 노드 추가
        workflow.add_node("analyze_intent", self._analyze_intent)
        workflow.add_node("search", self._run_agent("search"))
        workflow.add_node("planner", self._run_agent("planner"))
        workflow.add_node("calendar", self._run_agent("calendar"))
        workflow.add_node("mail", self._run_agent("mail"))
        workflow.add_node("recommendation", self._run_agent("recommendation"))
        workflow.add_node("determine_next_steps", self._determine_next_steps)

        # analyze_intent의 조건부 엣지
        workflow.add_conditional_edges(
            "analyze_intent",
            self._get_next_node,
            {
                "search": "search",
                "planner": "planner",
                "calendar": "calendar",
                "mail": "mail",
                "recommendation": "recommendation",
                "determine_next_steps": "determine_next_steps"
            }
        )

        # 에이전트 실행 후 다음 단계 결정
        workflow.add_edge("search", "determine_next_steps")
        workflow.add_edge("planner", "determine_next_steps")
        workflow.add_edge("calendar", "determine_next_steps")
        workflow.add_edge("mail", "determine_next_steps")
        workflow.add_edge("recommendation", "determine_next_steps")

        # determine_next_steps의 조건부 엣지
        # 1. next_steps가 없으면 워크플로우 종료
        # 2. next_steps가 있으면 해당 에이전트로 라우팅
        workflow.add_conditional_edges(
            "determine_next_steps",
            self._get_next_step_node,
            {
                "search": "search",
                "planner": "planner",
                "calendar": "calendar",
                "analyze_intent": "analyze_intent",
                "mail": "mail",
                "recommendation": "recommendation",
                "end": END
            }
        )

        # 시작 노드 설정
        workflow.set_entry_point("analyze_intent")

        return workflow.compile()

    async def _analyze_intent(self, state: AgentState) -> AgentState:
        """메시지 의도 분석"""
        messages = state["messages"]
        if not messages:
            return state



        session_id = state["session_id"]
        session_data = cache_client.get_conversation_history(session_id)

        # 이메일 입력 처리
        msg = messages[-1].content.strip()
        if "@" in msg and "." in msg and session_data.get("plan"):
            plan = session_data["plan"][-1]["data"]
            context = session_data["context"][-1]["data"]
            # 이메일을 컨텍스트에 추가
            process_search_and_mail.delay(
                email=msg,
                context=context,
                plan=plan
            )

            # 캘린더 등록 여부 확인
            state["result"] = {
                "status": "need_more_info",
                "message": "이메일이 등록되었습니다. 검색 결과는 이메일로 전송됩니다. 캘린더에 여행 일정을 등록하시겠습니까? (예/아니오)",
                "current_context": state["context"],
                "missing_fields": ["calendar_confirm"],
                "examples": {
                    "calendar_confirm": "예"
                }
            }
            state["next_steps"] = ["analyze_intent"]
            cache_client.add_message(session_id, {
                "type": "email",
                "data": email
            })
            return state
        # 현재 컨텍스트 가져오기

        before_contexts = session_data.get("context", [])
        if before_contexts:
            current_context = before_contexts[-1].get("data", {})
        else:
            current_context = {}

        # 캘린더 등록 확인 응답 처리
        if emails := session_data.get("email") and session_data.get("plan"):
            state["current_agent"] = "calendar"
            state["context"] = msg
            return state

        last_collected_info = session_data.get("collected_info", [])
        if last_collected_info:
            last_collected_info = last_collected_info[-1]["data"]
        # LLM을 사용하여 의도 분석
        prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template("""당신은 여행 계획 조율자입니다.
            사용자의 메시지를 분석하여 어떤 에이전트가 처리해야 할지 결정하세요.
            
            가능한 의도:
            1. planner: 여행 계획 수립, 일정 조정, 예산 계획 등
            2. calendar: 일정 등록, 일정 확인, 일정 수정 등
            3. recommendation: 여행지 추천, 여행 스타일 추천, 맞춤형 여행 계획 추천 등
            
            각 에이전트별 컨텍스트 (필수):
            - planner: {{
                "departure_location": "출발지 (필수)",
                "departure_date": "출발 날짜 (필수) (yyyy-mm-dd) (올해는 2025년)",
                "destination": "여행지 (필수)",
                "duration": "여행 기간 (필수)",
                "preferences": {{
                    "budget": "예산 (필수)",
                    "activities": ["선호 활동 (필수)"],
                    "accommodation": "숙박 선호도 (필수)",
                    "transportation": "교통수단 선호도 (필수)"
                }}
              }}
            - recommendation: {{
                "recommendation_step": "preferences|destination",
                "collected_info": {{
                    "travel_style": "여행 스타일",
                    "activities": ["선호 활동들"],
                    "budget": "예산 범위",
                    "accommodation": "숙박 선호도",
                    "transportation": "교통수단 선호도"
                }}
              }}
            
            현재까지의 컨텍스트:
            {current_context}
            
            이전 결과 데이터:
            {last_collected_info}
            
            중요: 
            1. 위의 현재 컨텍스트에 이미 있는 정보는 missing_info에 포함하지 마세요.
            2. 현재 컨텍스트의 정보를 먼저 확인하고, 그 다음에 새로운 정보를 추출하세요.
            3. 예를 들어, destination이 이미 컨텍스트에 있다면 missing_info의 fields에 포함시키지 마세요.
            4. 현재 컨텍스트, 이전 결과 데이터의 정보는 그대로 유지하고, 새로운 정보만 추가하세요.
            5. 현재 컨텍스트, 이전 결과 데이터의 값이 None이거나 빈 리스트인 경우에는 해당 필드가 아직 제공되지 않은 것으로 간주하세요.
            6. 이전에 추천을 통해서 정보를 얻었다면, 여행에 필요한 정보가 어느정도 채워질 때까지 추천을 하게 하세요.
            7. destination 정보가 없으면, planner를 쓰지 말고, destination 정보가 있으면, 이전 결과 데이터를 바탕으로 planner에 대한 extracted_context를 추출하세요.
            8. 사용자의 메시지에서 destination 정보를 추출했다면:
               - primary_intent를 "planner"로 설정하세요.
               - 이전 recommendation 단계에서 수집된 정보(preferences, activities 등)를 planner의 extracted_context에 포함시키세요.
               - recommendation 단계에서 수집된 정보가 있다면, 해당 정보를 planner의 preferences에 매핑하세요.
            
            메시지에서 직접 추출할 수 있는 정보는 extracted_context에 포함시켜주세요.
            현재 컨텍스트의 정보와 새로운 정보를 합쳐서 최종 컨텍스트를 구성하세요.
            
            응답은 반드시 다음 JSON 형식으로만 제공하세요. 다른 텍스트는 포함하지 마세요:
            {{
                "primary_intent": "planner|recommendation",
                "confidence": 0.0-1.0,
                "required_context": ["field1", "field2"],
                "suggested_next_steps": ["step1", "step2"],
                "extracted_context": {{
                    "field1": "추출된 값 1",
                    "field2": "추출된 값 2"
                }},
                "missing_info": {{
                    "fields": ["field1", "field2"],  # 현재 컨텍스트에 없는 필드만 포함
                    "message": "사용자에게 필요한 정보를 요청하는 메시지",
                    "examples": {{
                        "field1": "예시 값 1",
                        "field2": "예시 값 2"
                    }}
                }}
            }}"""),
            HumanMessage(content=messages[-1].content)
        ])

        # 컨텍스트를 구조화된 JSON으로 전달
        formatted_context = {
            "departure_location": current_context.get("departure_location"),
            "departure_date": current_context.get("departure_date"),
            "destination": current_context.get("destination"),
            "duration": current_context.get("duration"),
            "preferences": {
                "budget": current_context.get("preferences", {}).get("budget"),
                "activities": current_context.get("preferences", {}).get("activities", []),
                "accommodation": current_context.get("preferences", {}).get("accommodation"),
                "transportation": current_context.get("preferences", {}).get("transportation")
            },
            "recommendation": {
                "recommendation_step": current_context.get("recommendation_step"),
                "collected_info": {
                    "travel_style": current_context.get("collected_info", {}).get("travel_style"),
                    "activities": current_context.get("collected_info", {}).get("activities", []),
                    "budget": current_context.get("collected_info", {}).get("budget"),
                    "accommodation": current_context.get("collected_info", {}).get("accommodation"),
                    "transportation": current_context.get("collected_info", {}).get("transportation")
                }
            }
        }

        pp = prompt.format_messages(
            current_context=json.dumps(formatted_context, ensure_ascii=False, indent=2), last_collected_info=json.dumps(last_collected_info, ensure_ascii=False, indent=2) # 여기도 마지막것만 넣기 last_collected_info[-1]["data"]
        )

        response = await self.llm.ainvoke(pp)

        try:
            # JSON 파싱 시도
            intent_analysis = json.loads(response.content)

            # 현재 컨텍스트에 있는 필드가 missing_info에 포함되어 있는지 확인
            if intent_analysis.get("missing_info", {}).get("fields"):
                missing_fields = intent_analysis["missing_info"]["fields"]
                extracted_context = intent_analysis.get("extracted_context", {})

                def is_field_in_context(field: str, context: dict) -> bool:
                    """중첩된 필드가 컨텍스트에 있는지 확인"""
                    if "." in field:
                        parent, child = field.split(".")
                        return parent in context and context[parent] is not None and child in context[parent]
                    return field in context and context[field] is not None

                # 현재 컨텍스트와 extracted_context에 있는 필드는 missing_info에서 제거
                intent_analysis["missing_info"]["fields"] = [
                    field for field in missing_fields
                    if
                    not (is_field_in_context(field, current_context) or is_field_in_context(field, extracted_context))
                ]

                # missing_info가 비어있으면 제거
                if not intent_analysis["missing_info"]["fields"]:
                    intent_analysis.pop("missing_info", None)

            # 에이전트별 필수 컨텍스트 설정
            required_context = {
                "search": {
                    "query": None,
                    "location": None,
                    "type": None
                },
                "planner": {
                    "departure_location": None,
                    "departure_date": None,
                    "destination": None,
                    "duration": None,
                    "preferences": {
                        "budget": None,
                        "activities": [],
                        "accommodation": None,
                        "transportation": None
                    }
                },
                "calendar": {
                    "event_details": {
                        "title": None,
                        "start_date": None,
                        "end_date": None,
                        "location": None,
                        "description": None
                    }
                },
                "recommendation": {
                    "recommendation_step": None,
                    "collected_info": {
                        "travel_style": None,
                        "activities": [],
                        "budget": None,
                        "accommodation": None,
                        "transportation": None
                    }
                }
            }
            target_context = required_context.get(intent_analysis["primary_intent"], {})

            cache_client.add_message(session_id, {
                "type": "primary_intent",
                "data": intent_analysis["primary_intent"]
            })

            # 추출된 컨텍스트가 있는 경우 업데이트
            if intent_analysis.get("extracted_context"):
                for field, value in intent_analysis["extracted_context"].items():
                    if "." in field:
                        parent, child = field.split(".")
                        if parent not in target_context:
                            target_context[parent] = {}
                        if value is not None:  # None이 아닌 경우에만 업데이트
                            target_context[parent][child] = value
                    else:
                        if value is not None:  # None이 아닌 경우에만 업데이트
                            target_context[field] = value

            if intent_analysis["primary_intent"] == "recommendation":
                state["current_agent"] = "recommendation"
                state["context"] = update_dict(current_context, target_context)
                cache_client.add_message(session_id, {"type": "context", "data": state["context"]})
                state["next_steps"] = []
                return state

            # 누락된 정보가 있는 경우
            if intent_analysis.get("missing_info") and intent_analysis["missing_info"].get("fields"):
                examples = intent_analysis["missing_info"].get("examples", {})

                # 이전 컨텍스트 유지하면서 업데이트
                state["context"] = update_dict(current_context, target_context)
                cache_client.add_message(session_id, {"type": "context", "data": state["context"]})

                state["result"] = {
                    "status": "need_more_info",
                    "message": intent_analysis["missing_info"]["message"],
                    "missing_fields": missing_fields,
                    "examples": examples,
                    "current_context": state["context"]
                }
                state["next_steps"] = ["analyze_intent"]
                state["current_agent"] = None
            else:
                # 필요한 정보가 모두 있는 경우
                state["current_agent"] = intent_analysis["primary_intent"]
                state["context"] = update_dict(current_context, target_context)
                state["next_steps"] = intent_analysis["suggested_next_steps"]

            return state

        except json.JSONDecodeError:
            # JSON 파싱 실패 시 대화형 응답으로 처리
            state["result"] = {
                "status": "need_more_info",
                "message": response.content,
                "missing_fields": ["departure_location", "departure_date", "destination", "duration", "preferences"],
                "examples": {
                    "departure_location": "서울",
                    "departure_date": "2024-05-01",
                    "destination": "제주도",
                    "duration": "3박 4일",
                    "preferences": {
                        "budget": "100만원",
                        "activities": ["해변", "등산", "맛집"],
                        "accommodation": "호텔",
                        "transportation": "렌터카"
                    }
                },
                "current_context": state.get("context", {})  # 현재 컨텍스트 정보 추가
            }
            state["next_steps"] = ["analyze_intent"]
            state["current_agent"] = None
            return state

    def _run_agent(self, agent_name: str):
        """에이전트 실행 함수 생성"""

        async def run(state: AgentState) -> AgentState:
            agent = self.agents[agent_name]

            # 워크플로우 히스토리에 현재 단계 추가
            state["workflow_history"].append({
                "agent": agent_name,
                "input": state["messages"][-1].content,
                "context": state["context"]
            })


            result = await agent.process({
                "message": state["messages"][-1].content,
                "context": state["context"],
                "session_id": state["session_id"]
            })

            if agent_name == "search" and result.get("status") == "success":
                result["is_complete_search"] = True

            # 결과 저장
            state["result"] = result

            return state

        return run

    async def _determine_next_steps(self, state: AgentState) -> AgentState:
        """다음 단계 결정"""
        if not state["result"]:
            state["next_steps"] = []  # 결과가 없는 경우 워크플로우 종료
            return state

        # 에러 상태인 경우
        if state["result"].get("status") != "success":
            state["next_steps"] = []  # 실패 시 워크플로우 종료
            return state

        # 이전에 실행된 에이전트 목록 추출
        executed_agents = [
            step["agent"] for step in state["workflow_history"]
            if "agent" in step
        ]

        if "planner" in executed_agents:
            # 이메일 요청
            state["result"] = {
                "status": "need_more_info",
                "message": "여행 계획이 완성되었습니다. 이메일을 입력해주시면 상세한 장소 정보를 검색하고 메일로 보내드리겠습니다.",
                "missing_fields": ["email"],
                "examples": {
                    "email": "user@example.com"
                },
                "current_context": state["context"]
            }
            state["next_steps"] = []  # 워크플로우 일시 중단
            return state

        # LLM을 사용하여 다음 단계 결정
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""당신은 여행 계획 조율자입니다.
            현재까지의 작업 결과를 바탕으로 다음 단계를 결정하세요.
            
            워크플로우 히스토리:
            {history}
            
            현재 결과:
            {result}
            
            이미 실행된 에이전트:
            {executed_agents}
            
            사용 가능한 에이전트:
            - planner: 여행 계획 수립, 일정 조정, 예산 계획 등
            - recommendation: 여행지 추천, 여행 스타일 추천, 맞춤형 여행 계획 추천 등
            
            응답 형식:
            {{
                "is_complete": true/false,
                "next_steps": ["planner"]  # 다음에 실행할 에이전트 목록
            }}
            
            주의사항:
            1. 이미 실행된 에이전트는 다시 실행하지 마세요.
            2. 각 에이전트는 한 번만 실행되어야 합니다.
            3. 모든 필요한 에이전트가 실행되었다면 is_complete를 true로 설정하세요.
            4. recommendation 에이전트는 한 번만 실행되어야 하며, 이미 실행되었다면 다시 실행하지 마세요.
            5. recommendation 에이전트가 현재 실행 중이라면 next_steps에 포함시키지 마세요."""),
            HumanMessage(content="다음 단계를 결정해주세요.")
        ])

        # 다음 단계 결정 실행
        response = await self.llm.ainvoke(prompt.format_messages(
            history=str(state["workflow_history"]),
            result=str(state["result"]),
            executed_agents=str(executed_agents)
        ))
        next_steps_analysis = json.loads(response.content)

        # 상태 업데이트
        if next_steps_analysis["is_complete"] or not next_steps_analysis["next_steps"]:
            state["next_steps"] = []
        else:
            # next_steps가 유효한 에이전트 이름이고 이전에 실행되지 않은 에이전트인지 확인
            valid_agents = set(self.agents.keys())
            state["next_steps"] = [
                step for step in next_steps_analysis["next_steps"]
                if step in valid_agents and step not in executed_agents
            ]

        return state

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """메시지 처리 및 워크플로우 실행"""
        if not input_data.get("message"):
            return {"error": "Invalid message"}

        # 이전 메시지 히스토리 가져오기
        previous_messages = [
            HumanMessage(content=msg["content"]) if isinstance(msg, dict) else msg
            for msg in input_data.get("messages", [])
        ]

        # 초기 상태 설정
        initial_state = {
            "messages": [*previous_messages, HumanMessage(content=input_data["message"])],
            "current_agent": None,
            "context": input_data.get("context", {}),
            "result": None,
            "workflow_history": [],
            "next_steps": []
        }

        # 워크플로우 실행
        final_state = await self.workflow.ainvoke(initial_state)

        return {
            "status": "success",
            "result": final_state["result"],
            "workflow_history": final_state["workflow_history"],
            "messages": final_state["messages"]  # 메시지 히스토리 반환
        }

    async def process_stream(self, input_data: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """메시지 스트리밍 처리 및 워크플로우 실행"""
        if not input_data.get("message"):
            yield {"status": "error", "result": "Invalid message"}
            return

        # 이전 메시지 히스토리 가져오기
        previous_messages = [
            HumanMessage(content=msg["content"]) if isinstance(msg, dict) else msg
            for msg in input_data.get("messages", [])
        ]

        # 초기 상태 설정
        initial_state = {
            "messages": [*previous_messages, HumanMessage(content=input_data["message"])],
            "current_agent": None,
            "context": input_data.get("context", {}),
            "session_id": input_data["session_id"],
            "workflow_history": input_data.get("workflow_history", []),  # 이전 워크플로우 히스토리 유지
            "next_steps": []
        }

        # 워크플로우 실행
        async for state in self.workflow.astream(initial_state):
            if not state:  # 상태가 None인 경우 건너뛰기
                continue

            # 현재 실행 중인 노드의 상태 가져오기
            try:
                current_node = next(iter(state.keys()))
                current_state = state[current_node]
            except (StopIteration, KeyError):  # 상태가 비어있거나 키가 없는 경우
                continue

            if not current_state:  # current_state가 None인 경우 건너뛰기
                continue

            # analyze_intent 노드 처리
            if current_node == "analyze_intent":
                if current_state.get("result") is not None and current_state.get("result", {}).get(
                        "status") == "need_more_info":
                    yield {
                        "status": "need_more_info",
                        "result": current_state["result"],
                        "messages": current_state["messages"]
                    }
                continue

            # 일반적인 처리 상태
            if current_state.get("result"):
                if current_state["result"].get("status") == "processing":
                    # 진행 상황 메시지 생성
                    progress_message = None
                    if current_node == "planner":
                        progress_message = "여행 계획을 수립하고 있습니다..."
                    elif current_node == "search":
                        progress_message = "장소 정보를 검색하고 있습니다..."

                    yield {
                        "status": "processing",
                        "result": current_state["result"],
                        "messages": current_state["messages"],
                        "output_message": progress_message
                    }
                elif current_state["result"].get("status") != "need_more_info":
                    yield {
                        "status": "success",
                        "result": current_state["result"],
                        "messages": current_state["messages"]
                    }
                else:
                    yield {
                        "status": "need_more_info",
                        "result": current_state["result"],
                        "messages": current_state["messages"]
                    }
            elif current_state.get("current_agent"):
                # 현재 에이전트의 상태를 스트리밍
                progress_message = None
                if current_state["current_agent"] == "planner":
                    progress_message = "여행 계획 에이전트가 작업을 시작합니다..."
                elif current_state["current_agent"] == "search":
                    progress_message = "장소 검색 에이전트가 작업을 시작합니다..."

                yield {
                    "status": "processing",
                    "result": current_state["result"],
                    "messages": current_state["messages"],
                    "output_message": progress_message
                }
