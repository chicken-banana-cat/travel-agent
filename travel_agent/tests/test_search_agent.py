import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

# 환경변수 설정을 먼저 수행
env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    # .env 파일이 없는 경우 테스트용 환경변수 설정
    os.environ["OPENAI_API_KEY"] = "test-key"
    os.environ["MODEL_NAME"] = "gpt-3.5-turbo"
    os.environ["NAVER_CLIENT_ID"] = "test-client-id"
    os.environ["NAVER_CLIENT_SECRET"] = "test-client-secret"

from travel_agent.core.agents.search_agent import SearchAgent


@pytest.fixture(autouse=True)
def setup_env():
    """테스트에 필요한 환경변수 설정"""
    # 이미 모듈 import 전에 환경변수가 설정되어 있으므로
    # 여기서는 추가 설정이 필요 없음
    yield

    # 테스트 후 환경변수 정리 (테스트용 환경변수만)
    if not env_path.exists():
        for key in [
            "OPENAI_API_KEY",
            "MODEL_NAME",
            "NAVER_CLIENT_ID",
            "NAVER_CLIENT_SECRET",
        ]:
            os.environ.pop(key, None)


@pytest.fixture
def search_agent():
    return SearchAgent()


@pytest.fixture
def test_input():
    return {
        "message": "1박당 20만원 아래면 좋겠네",
        "context": {
            "destination": "부산",
            "duration": "3일",
            "preferences": {
                "budget": "1박당 20만원 이하",
                "activities": ["국밥먹기"],
                "transportation": "대중교통",
            },
            "query": "호텔",
            "location": "부산",
            "type": "호텔",
        },
        "previous_result": {
            "status": "success",
            "plan": {
                "itinerary": [
                    {
                        "day": 1,
                        "activities": [
                            {
                                "time": "09:00",
                                "activity": "부산 도착 및 숙소 체크인",
                                "location": "부산역 인근 호텔",
                                "duration": "1시간",
                                "cost": 180000,
                            },
                            {
                                "time": "10:15",
                                "activity": "부산 시내 대중교통 이용하여 광안리 해수욕장 방문",
                                "location": "광안리 해수욕장",
                                "duration": "2시간",
                                "cost": 3000,
                            },
                            {
                                "time": "12:30",
                                "activity": "국밥 식사 (돼지국밥 또는 곰탕 등)",
                                "location": "광안리 국밥 골목",
                                "duration": "1시간",
                                "cost": 8000,
                            },
                            {
                                "time": "13:45",
                                "activity": "광안대교 전망 및 산책",
                                "location": "광안리 해변",
                                "duration": "1시간 30분",
                                "cost": 0,
                            },
                            {
                                "time": "15:30",
                                "activity": "숙소 휴식 및 자유시간",
                                "location": "호텔",
                                "duration": "3시간",
                                "cost": 0,
                            },
                            {
                                "time": "18:30",
                                "activity": "자갈치 시장 방문 및 해산물 구경",
                                "location": "자갈치 시장",
                                "duration": "2시간",
                                "cost": 5000,
                            },
                        ],
                    },
                    {
                        "day": 2,
                        "activities": [
                            {
                                "time": "08:00",
                                "activity": "호텔 조식",
                                "location": "호텔 식당",
                                "duration": "1시간",
                                "cost": 15000,
                            },
                            {
                                "time": "09:30",
                                "activity": "대중교통 이용하여 감천문화마을 방문",
                                "location": "감천문화마을",
                                "duration": "2시간 30분",
                                "cost": 3000,
                            },
                            {
                                "time": "12:15",
                                "activity": "국밥 식사 (부산 전통 돼지국밥)",
                                "location": "감천동 인근 국밥집",
                                "duration": "1시간",
                                "cost": 8000,
                            },
                            {
                                "time": "13:30",
                                "activity": "부산 영화의 전당 방문",
                                "location": "영화의 전당",
                                "duration": "1시간 30분",
                                "cost": 0,
                            },
                            {
                                "time": "15:30",
                                "activity": "해운대 해수욕장 방문 및 산책",
                                "location": "해운대 해수욕장",
                                "duration": "2시간",
                                "cost": 0,
                            },
                            {
                                "time": "18:00",
                                "activity": "숙소 귀환 및 휴식",
                                "location": "호텔",
                                "duration": "2시간",
                                "cost": 0,
                            },
                        ],
                    },
                    {
                        "day": 3,
                        "activities": [
                            {
                                "time": "08:00",
                                "activity": "호텔 체크아웃 및 조식",
                                "location": "호텔 식당",
                                "duration": "1시간",
                                "cost": 15000,
                            },
                            {
                                "time": "09:30",
                                "activity": "대중교통으로 부산 타워 방문 및 전망 감상",
                                "location": "부산 타워",
                                "duration": "1시간 30분",
                                "cost": 8000,
                            },
                            {
                                "time": "11:30",
                                "activity": "국밥 식사 (마지막 식사로 돼지국밥 추천)",
                                "location": "부산 중구 국밥 거리",
                                "duration": "1시간",
                                "cost": 8000,
                            },
                            {
                                "time": "12:45",
                                "activity": "부산역으로 이동 및 기념품 쇼핑",
                                "location": "부산역",
                                "duration": "1시간 15분",
                                "cost": 10000,
                            },
                            {
                                "time": "14:00",
                                "activity": "부산 출발",
                                "location": "부산역",
                                "duration": "이동시간",
                                "cost": 0,
                            },
                        ],
                    },
                ],
                "budget": {
                    "transportation": {
                        "estimated": 21000.0,
                        "details": [{"item": "도시철도 및 버스 3일권", "cost": 21000}],
                    },
                    "accommodation": {
                        "estimated": 360000.0,
                        "details": [
                            {"item": "호텔 2박 (1박 18만원 예상)", "cost": 360000}
                        ],
                    },
                    "food": {
                        "estimated": 72000.0,
                        "details": [
                            {"item": "국밥 3회 식사", "cost": 24000},
                            {"item": "호텔 조식 2회", "cost": 30000},
                            {"item": "기타 식비 및 간식", "cost": 18000},
                        ],
                    },
                    "activities": {
                        "estimated": 8000.0,
                        "details": [{"item": "부산 타워 입장료", "cost": 8000}],
                    },
                    "total": 460000.0,
                },
                "recommendations": [
                    {"category": "음식", "items": ["돼지국밥", "곰탕", "해산물"]},
                    {
                        "category": "주요 관광지",
                        "items": [
                            "광안리 해수욕장",
                            "감천문화마을",
                            "해운대 해수욕장",
                            "부산 타워",
                            "자갈치 시장",
                        ],
                    },
                ],
                "tips": [
                    "부산 내 대중교통은 1일권 또는 3일권 이용 시 편리하고 경제적입니다.",
                    "국밥은 부산의 대표 음식이므로 다양한 국밥집을 방문해보세요.",
                    "호텔은 1박 20만원 이하로 예약 가능하나, 미리 예약하는 것이 좋습니다.",
                    "해운대와 광안리는 저녁 노을과 야경이 아름다우니 방문 시간을 고려하세요.",
                    "자갈치 시장에서는 신선한 해산물을 구경하고 가벼운 식사도 가능합니다.",
                ],
            },
            "error": None,
            "message": None,
        },
    }


@pytest.mark.asyncio
async def test_search_agent_process(search_agent, test_input):
    # 검색 실행
    result = await search_agent.process(test_input)

    # 기본 검증
    assert result["status"] == "success"
    assert "context" in result
    assert "preferences" in result["context"]
    assert "places" in result["context"]["preferences"]

    # 장소 정보 검증
    places = result["context"]["preferences"]["places"]
    assert len(places) > 0

    # 각 장소의 필수 필드 검증
    for place in places:
        assert "name" in place
        assert "type" in place
        assert "location" in place
        assert "description" in place
        assert "address" in place["location"]
        assert "coordinates" in place["location"]


@pytest.mark.asyncio
async def test_search_agent_validation(search_agent):
    # 유효하지 않은 입력 테스트
    invalid_input = {"context": {}}
    result = await search_agent.process(invalid_input)
    assert result["status"] == "error"
    assert "error" in result


@pytest.mark.asyncio
async def test_search_agent_error_handling(search_agent, test_input, monkeypatch):
    # LLM 호출 실패 시뮬레이션
    async def mock_llm_ainvoke(*args, **kwargs):
        raise Exception("LLM API Error")

    monkeypatch.setattr(search_agent.llm, "ainvoke", mock_llm_ainvoke)

    result = await search_agent.process(test_input)
    assert result["status"] == "error"
    assert "error" in result
