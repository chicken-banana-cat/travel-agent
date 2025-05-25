import asyncio
import json
import logging
import time
from typing import Any, Dict, List

import aiohttp
from langchain.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage

from ..config.settings import settings
from .base import BaseAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SearchAgent(BaseAgent):
    """여행 장소 검색을 담당하는 에이전트"""

    def __init__(self):
        super().__init__(
            name="search_agent",
            description="여행 장소 검색 및 정보 수집을 담당하는 에이전트",
        )
        self.prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessage(
                    content="""당신은 여행 장소 검색 전문가입니다.
            사용자의 요구사항에 맞는 여행지를 검색하고, 관련 정보를 제공합니다.
            항상 정확하고 신뢰할 수 있는 정보만을 제공하세요."""
                ),
                HumanMessage(content="{query}"),
            ]
        )
        self.naver_client_id = settings.NAVER_CLIENT_ID
        self.naver_client_secret = settings.NAVER_CLIENT_SECRET
        # 동시 LLM API 호출 제한
        self.llm_semaphore = asyncio.Semaphore(3)  # 최대 3개의 동시 호출 허용
        # 네이버 API 호출 제한 (초당 10개)
        self.naver_semaphore = asyncio.Semaphore(3)

    async def validate(self, input_data: Dict[str, Any]) -> bool:
        """검색 쿼리 유효성 검증"""
        return bool(input_data.get("plan"))

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """검색 처리"""
        context = input_data.get("context", {})
        plan = input_data.get("plan", {})
        if not await self.validate(input_data):
            return {
                "status": "error",
                "error": "Invalid search query",
                "message": "검색 쿼리가 누락되었습니다.",
            }

        try:
            locations = []
            for day in plan.get("itinerary", []):
                for activity in day.get("activities", []):
                    location = activity.get("location", "")
                    if location and location not in locations:
                        locations.append(location)

            # 추천 장소 추가
            for rec in plan.get("recommendations", []):
                if rec.get("category") in ["관광지", "쇼핑"]:
                    locations.extend(rec.get("items", []))

            # 1. LLM을 통한 검색 의도 파악
            intent_prompt = ChatPromptTemplate.from_messages(
                [
                    SystemMessage(
                        content="""당신은 여행 검색 의도 분석 전문가입니다.
                주어진 장소 목록을 분석하여 각 장소의 검색 유형과 특성을 파악해주세요.
                
                응답은 다음 JSON 형식으로 제공해주세요:
                {
                    "locations": [
                        {
                            "name": "장소명",
                            "search_type": "장소/호텔/음식점/관광지",
                            "keywords": ["검색 키워드1", "검색 키워드2"],
                            "priority": 1-5  // 검색 우선순위
                        }
                    ],
                    "common_preferences": {
                        "price_range": "가격대",
                        "style": "스타일",
                        "features": ["특성1", "특성2"]
                    }
                }"""
                    ),
                    HumanMessage(
                        content=f"""여행 계획의 장소들:
                {locations}
                
                여행 선호사항:
                {context.get('preferences', {})}"""
                    ),
                ]
            )

            # 검색 의도 분석
            intent_response = await self.llm.ainvoke(intent_prompt.format_messages())
            search_intent = json.loads(intent_response.content)

            # 2. 각 장소별 상세 정보 검색
            async def process_location(
                location_info: Dict[str, Any]
            ) -> List[Dict[str, Any]]:
                if location_info["priority"] < 4:
                    return []

                search_query = {
                    "name": location_info["name"],
                    "search_type": location_info["search_type"],
                }

                # 장소 검색
                search_results = await self._search_places(search_query)

                # 상세 정보 수집
                detailed_results = await self._enrich_place_details(search_results)

                # 결과에 우선순위와 원본 장소명 추가
                for result in detailed_results:
                    result["priority"] = location_info["priority"]
                    result["original_name"] = location_info["name"]

                return detailed_results

            # 모든 장소를 병렬로 처리
            all_results = await asyncio.gather(
                *[process_location(loc) for loc in search_intent["locations"]]
            )

            # 결과 병합
            all_place_details = []
            for results in all_results:
                all_place_details.extend(results)

            # 3. 최종 결과 정리
            # 요약 메시지 생성
            summary_prompt = ChatPromptTemplate.from_messages(
                [
                    SystemMessage(
                        content="""당신은 여행 정보 요약 전문가입니다.
                주어진 장소 정보들과 여행 계획을 바탕으로 상세하고 명확한 요약 메시지를 작성해주세요.
                다음 정보를 포함해주세요:
                1. 여행 일정 개요 (기간, 주요 일정)
                2. 검색된 주요 장소들의 종류와 수
                3. 주요 관심사 (예: 호텔, 관광지, 음식점 등)
                4. 예산 범위와 선호사항
                5. 일별 주요 일정과 추천 활동
                6. 특별한 추천 사항과 팁
                
                응답은 50문장보다 적게 작성해주세요."""
                    ),
                    HumanMessage(
                        content=f"""여행 계획:
                {json.dumps(plan, ensure_ascii=False, indent=2)}
                
                검색된 장소들:
                {json.dumps(all_place_details, ensure_ascii=False, indent=2)}
                
                검색 의도:
                {json.dumps(search_intent, ensure_ascii=False, indent=2)}
                
                사용자 선호사항:
                {json.dumps(context.get('preferences', {}), ensure_ascii=False, indent=2)}"""
                    ),
                ]
            )

            summary_response = await self.llm.ainvoke(summary_prompt.format_messages())

            final_results = {
                "status": "success",
                "message": summary_response.content,
                "context": {
                    "destination": context["destination"],
                    "duration": context.get("duration", "3박 4일"),
                    "preferences": {
                        "places": all_place_details,
                        "search_intent": search_intent,
                        "user_preferences": context.get("preferences", {}),
                    },
                },
            }

            return final_results

        except Exception as e:
            logger.error(exc_info=e, msg="이메일 전송 중 오류")
            return {
                "status": "error",
                "error": "Search failed",
                "message": f"장소 검색 중 오류가 발생했습니다: {str(e)}",
            }

    async def _search_places(
        self, search_intent: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """네이버 검색 API를 통한 장소 검색"""
        if not self.naver_client_id or not self.naver_client_secret:
            raise ValueError("Naver API credentials are not configured")

        query = search_intent.get("name", "")
        if not query:
            return []

        base_url = "https://openapi.naver.com/v1/search/local.json"
        params = {"query": query, "display": 2, "start": 1, "sort": "random"}

        headers = {
            "X-Naver-Client-Id": self.naver_client_id,
            "X-Naver-Client-Secret": self.naver_client_secret,
            "Accept": "application/json",
        }

        return await self._execute_search_with_retry(
            base_url, params, headers, search_intent
        )

    async def _execute_search_with_retry(
        self,
        base_url: str,
        params: Dict[str, Any],
        headers: Dict[str, str],
        search_intent: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """재시도 로직이 포함된 검색 실행"""
        max_retries = 3
        retry_count = 0
        retry_delay = 10

        async with aiohttp.ClientSession() as session:
            while retry_count < max_retries:
                try:
                    return await self._make_search_request(
                        session, base_url, params, headers, search_intent
                    )
                except Exception as e:
                    retry_count += 1
                    if retry_count >= max_retries:
                        print(f"Error during API call: {str(e)}")
                        raise

                    print(
                        f"Error during API call: {str(e)}. Retrying in {retry_delay} seconds... (Attempt {retry_count}/{max_retries})"
                    )
                    await asyncio.sleep(retry_delay)

    async def _make_search_request(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        params: Dict[str, Any],
        headers: Dict[str, str],
        search_intent: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """단일 검색 요청 실행"""
        async with self.naver_semaphore:
            async with session.get(
                base_url, params=params, headers=headers
            ) as response:
                print(f"Response status: {response.status}")
                print(f"Response URL: {str(response.url)}")

                if response.status == 429:
                    raise Exception("Rate limit exceeded")

                if response.status != 200:
                    error_text = await response.text()
                    print(f"Error response: {error_text}")
                    raise Exception(
                        f"Naver API request failed with status {response.status}: {error_text}"
                    )

                data = await response.json()
                print(f"Response data: {data}")

                return self._convert_search_results(data, search_intent)

    def _convert_search_results(
        self, data: Dict[str, Any], search_intent: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """검색 결과를 장소 객체로 변환"""
        places = []
        for item in data.get("items", []):
            place = {
                "id": item.get("link", ""),
                "name": item.get("title", "").replace("<b>", "").replace("</b>", ""),
                "type": search_intent.get("search_type", "장소"),
                "location": {
                    "address": item.get("address", ""),
                    "road_address": item.get("roadAddress", ""),
                    "coordinates": {
                        "x": item.get("mapx", ""),
                        "y": item.get("mapy", ""),
                    },
                },
                "category": item.get("category", ""),
                "description": item.get("description", ""),
                "contact": item.get("telephone", ""),
                "link": item.get("link", ""),
            }
            places.append(place)
        return places

    async def _enrich_place_details(
        self, places: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """장소 상세 정보 수집"""

        async def enrich_place(place: Dict[str, Any]) -> Dict[str, Any]:
            start_time = time.time()
            print(f"Starting LLM call for place: {place['name']}")
            try:
                async with self.llm_semaphore:  # LLM API 호출 제한
                    # LLM을 통한 장소 설명 생성
                    description_prompt = ChatPromptTemplate.from_messages(
                        [
                            SystemMessage(
                                content="""당신은 여행 장소 설명 전문가입니다.
                        주어진 장소에 대한 매력적인 설명을 작성해주세요.
                        다음 정보를 포함해주세요:
                        1. 장소의 주요 특징
                        2. 방문하기 좋은 시간
                        3. 주변 관광지
                        4. 교통 정보
                        5. 방문 팁"""
                            ),
                            HumanMessage(
                                content=f"장소: {place['name']}, 위치: {place['location']['address']}, 카테고리: {place['category']}"
                            ),
                        ]
                    )

                    description_response = await self.llm.ainvoke(
                        description_prompt.format_messages()
                    )
                    end_time = time.time()
                    print(
                        f"Completed LLM call for {place['name']} in {end_time - start_time:.2f} seconds"
                    )

                    return {
                        **place,
                        "description": description_response.content,
                        "details": {
                            "contact": place.get("contact", ""),
                            "website": place.get("link", ""),
                            "category": place.get("category", ""),
                            "coordinates": place["location"]["coordinates"],
                            "address": {
                                "street": place["location"]["road_address"],
                                "full": place["location"]["address"],
                            },
                        },
                    }
            except Exception as e:
                end_time = time.time()
                print(
                    f"Failed LLM call for {place['name']} after {end_time - start_time:.2f} seconds: {str(e)}"
                )
                raise

        print(
            f"Processing {len(places)} places with semaphore limit {self.llm_semaphore._value}"
        )
        # 모든 장소의 설명을 병렬로 생성 (rate limited)
        enriched_places = await asyncio.gather(
            *[enrich_place(place) for place in places],
            return_exceptions=True,  # 예외가 발생해도 다른 요청은 계속 진행
        )

        # 실패한 요청 필터링
        successful_places = []
        for place in enriched_places:
            if isinstance(place, Exception):
                print(f"Failed to process place: {str(place)}")
            else:
                successful_places.append(place)

        return successful_places
