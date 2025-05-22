import pytest
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

# 환경변수 설정을 먼저 수행
env_path = Path(__file__).parent.parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)
else:
    # .env 파일이 없는 경우 테스트용 환경변수 설정
    os.environ["OPENAI_API_KEY"] = "test-key"
    os.environ["MODEL_NAME"] = "gpt-3.5-turbo"

# settings 모듈을 먼저 import
from travel_agent.core.config.settings import settings
from travel_agent.core.agents.orchestrator import Orchestrator
from langchain_core.messages import HumanMessage

@pytest.fixture(autouse=True)
def setup_env():
    """테스트에 필요한 환경변수 설정"""
    yield
    
    # 테스트 후 환경변수 정리 (테스트용 환경변수만)
    if not env_path.exists():
        for key in ["OPENAI_API_KEY", "MODEL_NAME"]:
            os.environ.pop(key, None)

@pytest.fixture
def orchestrator():
    return Orchestrator()

@pytest.fixture
def test_input():
    return {
        'message': '부산으로 3박 4일 여행 계획을 세워주세요',
        'context': {
            'departure_location': '서울',
            'departure_date': '2024-05-01',
            'destination': '부산',
            'duration': '3박 4일',
            'preferences': {
                'budget': '1박당 20만원 이하',
                'activities': ['해변', '맛집'],
                'accommodation': '호텔',
                'transportation': '대중교통'
            }
        }
    }

@pytest.mark.asyncio
async def test_analyze_intent_basic(orchestrator, test_input):
    """기본적인 의도 분석 테스트"""
    # 초기 상태 설정
    state = {
        "messages": [HumanMessage(content=test_input['message'])],
        "current_agent": None,
        "context": test_input['context'],
        "result": None,
        "workflow_history": [],
        "next_steps": []
    }
    
    # 의도 분석 실행
    result = await orchestrator._analyze_intent(state)
    
    # 기본 검증
    assert result["current_agent"] == "planner"
    assert "context" in result
    assert result["context"]["destination"] == "부산"
    assert result["context"]["duration"] == "3박 4일"
    assert "preferences" in result["context"]

@pytest.mark.asyncio
async def test_analyze_intent_missing_required_fields(orchestrator):
    """필수 필드가 누락된 경우 테스트"""
    # 필수 필드가 누락된 입력
    state = {
        "messages": [HumanMessage(content="부산으로 여행 가고 싶어요")],
        "current_agent": None,
        "context": {
            "destination": "부산"
            # departure_location, departure_date, duration 누락
        },
        "result": None,
        "workflow_history": [],
        "next_steps": []
    }
    
    # 의도 분석 실행
    result = await orchestrator._analyze_intent(state)
    
    # 에러 상태 검증
    assert result["result"]["status"] == "need_more_info"
    assert "missing_fields" in result["result"]
    assert "departure_location" in result["result"]["missing_fields"]
    assert "departure_date" in result["result"]["missing_fields"]
    assert "duration" in result["result"]["missing_fields"]

@pytest.mark.asyncio
async def test_analyze_intent_email_after_plan(orchestrator):
    """여행 계획 완료 후 이메일 입력 테스트"""
    # 여행 계획이 완료된 상태에서 이메일 입력
    state = {
        "messages": [HumanMessage(content="user@example.com")],
        "current_agent": None,
        "context": {
            "departure_location": "서울",
            "departure_date": "2024-05-01",
            "destination": "부산",
            "duration": "3박 4일",
            "preferences": {
                "budget": "1박당 20만원 이하",
                "activities": ["해변", "맛집"]
            }
        },
        "result": {
            "previous_result": {
                "status": "success",
                "is_complete_search": True
            }
        },
        "workflow_history": [],
        "next_steps": []
    }
    
    # 의도 분석 실행
    result = await orchestrator._analyze_intent(state)
    
    # 이메일 처리 검증
    assert result["current_agent"] == "mail"
    assert result["context"]["email"] == "user@example.com"
    assert result["next_steps"] == ["mail"]

@pytest.mark.asyncio
async def test_analyze_intent_email_before_plan(orchestrator):
    """여행 계획 완료 전 이메일 입력 테스트"""
    # 여행 계획이 완료되지 않은 상태에서 이메일 입력
    state = {
        "messages": [HumanMessage(content="user@example.com")],
        "current_agent": None,
        "context": {
            "departure_location": "서울",
            "departure_date": "2024-05-01",
            "destination": "부산",
            "duration": "3박 4일"
        },
        "result": None,
        "workflow_history": [],
        "next_steps": []
    }
    
    # 의도 분석 실행
    result = await orchestrator._analyze_intent(state)
    
    # 에러 상태 검증
    assert result["result"]["status"] == "need_more_info"
    assert "message" in result["result"]
    assert "여행 계획이 완성된 후에 이메일을 입력해주세요" in result["result"]["message"]

@pytest.mark.asyncio
async def test_analyze_intent_error_handling(orchestrator, monkeypatch):
    """에러 처리 테스트"""
    # LLM 호출 실패 시뮬레이션
    async def mock_llm_ainvoke(*args, **kwargs):
        raise Exception("LLM API Error")
    
    monkeypatch.setattr(orchestrator.llm, "ainvoke", mock_llm_ainvoke)
    
    state = {
        "messages": [HumanMessage(content="부산으로 여행 가고 싶어요")],
        "current_agent": None,
        "context": {},
        "result": None,
        "workflow_history": [],
        "next_steps": []
    }
    
    # 의도 분석 실행
    result = await orchestrator._analyze_intent(state)
    
    # 에러 상태 검증
    assert result["result"]["status"] == "need_more_info"
    assert "missing_fields" in result["result"]
    assert "examples" in result["result"] 