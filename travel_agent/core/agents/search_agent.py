from typing import Any, Dict, List
import os
import aiohttp
from urllib.parse import quote
import json

from langchain.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage

from .base import BaseAgent


class SearchAgent(BaseAgent):
    """여행 장소 검색을 담당하는 에이전트"""
    
    def __init__(self):
        super().__init__(
            name="search_agent",
            description="여행 장소 검색 및 정보 수집을 담당하는 에이전트"
        )
        self.prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""당신은 여행 장소 검색 전문가입니다.
            사용자의 요구사항에 맞는 여행지를 검색하고, 관련 정보를 제공합니다.
            항상 정확하고 신뢰할 수 있는 정보만을 제공하세요."""),
            HumanMessage(content="{query}")
        ])
        self.naver_client_id = os.getenv("NAVER_CLIENT_ID")
        self.naver_client_secret = os.getenv("NAVER_CLIENT_SECRET")
    
    async def validate(self, input_data: Dict[str, Any]) -> bool:
        """검색 쿼리 유효성 검증"""
        return bool(input_data.get("plan"))
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """검색 처리"""
        context = input_data.get("context", {})
        input_data = input_data["previous_result"]
        if not await self.validate(input_data):
            return {
                "status": "error",
                "error": "Invalid search query",
                "message": "검색 쿼리가 누락되었습니다."
            }
        
        try:
            # planner의 결과에서 장소 정보 추출
            plan = input_data.get("plan", {})

            # 일정에서 장소 추출
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
            intent_prompt = ChatPromptTemplate.from_messages([
                SystemMessage(content="""당신은 여행 검색 의도 분석 전문가입니다.
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
                }"""),
                HumanMessage(content=f"""여행 계획의 장소들:
                {locations}
                
                여행 선호사항:
                {context.get('preferences', {})}""")
            ])
            
            # 검색 의도 분석
            intent_response = await self.llm.ainvoke(intent_prompt.format_messages())
            search_intent = json.loads(intent_response.content)
            
            # 2. 각 장소별 상세 정보 검색
            all_place_details = []
            for location_info in search_intent["locations"]:
                # 단순화된 검색 쿼리
                if location_info['priority'] < 5:
                    continue
                search_query = {
                    "name": location_info["name"],
                    "search_type": location_info["search_type"]
                }
                
                # 장소 검색
                search_results = await self._search_places(search_query)
                
                # 상세 정보 수집
                detailed_results = await self._enrich_place_details(search_results)
                
                # 결과에 우선순위와 원본 장소명 추가
                for result in detailed_results:
                    result["priority"] = location_info["priority"]
                    result["original_name"] = location_info["name"]
                
                all_place_details.extend(detailed_results)
            
            # 3. 최종 결과 정리
            final_results = {
                "status": "success",
                "message": "장소 검색이 완료되었습니다.",
                "context": {
                    "destination": input_data["context"]["destination"],
                    "duration": input_data["context"].get("duration", "3박 4일"),
                    "preferences": {
                        "places": all_place_details,
                        "search_intent": search_intent,
                        "user_preferences": input_data["context"].get("preferences", {})
                    }
                }
            }
            
            return final_results
            
        except Exception as e:
            return {
                "status": "error",
                "error": "Search failed",
                "message": f"장소 검색 중 오류가 발생했습니다: {str(e)}"
            }
    
    async def _search_places(self, search_intent: Dict[str, Any]) -> List[Dict[str, Any]]:
        """네이버 검색 API를 통한 장소 검색"""
        if not self.naver_client_id or not self.naver_client_secret:
            raise ValueError("Naver API credentials are not configured")
        
        # 검색 쿼리 구성 - 단순히 장소명만 사용
        query = search_intent.get("name", "")
        if not query:
            return []
        
        # API 요청 URL 구성
        base_url = "https://openapi.naver.com/v1/search/local.json"
        params = {
            "query": query,
            "display": 10,
            "start": 1,
            "sort": "random"
        }
        
        # 실제 요청 URL 확인
        request_url = f"{base_url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
        print(f"Request URL: {request_url}")
        
        headers = {
            "X-Naver-Client-Id": self.naver_client_id,
            "X-Naver-Client-Secret": self.naver_client_secret,
            "Accept": "application/json"
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(base_url, params=params, headers=headers) as response:
                    print(f"Response status: {response.status}")
                    print(f"Response URL: {str(response.url)}")  # 실제 요청된 URL 확인
                    
                    if response.status != 200:
                        error_text = await response.text()
                        print(f"Error response: {error_text}")
                        raise Exception(f"Naver API request failed with status {response.status}: {error_text}")
                    
                    data = await response.json()
                    print(f"Response data: {data}")
                    
                    # 검색 결과 변환
                    places = []
                    for item in data.get("items", []):
                        place = {
                            "id": item.get("link", ""),  # 고유 식별자로 link 사용
                            "name": item.get("title", "").replace("<b>", "").replace("</b>", ""),
                            "type": search_intent.get("search_type", "장소"),
                            "location": {
                                "address": item.get("address", ""),
                                "road_address": item.get("roadAddress", ""),
                                "coordinates": {
                                    "x": item.get("mapx", ""),
                                    "y": item.get("mapy", "")
                                }
                            },
                            "category": item.get("category", ""),
                            "description": item.get("description", ""),
                            "contact": item.get("telephone", ""),
                            "link": item.get("link", "")
                        }
                        places.append(place)
                    
                    return places
            except Exception as e:
                print(f"Error during API call: {str(e)}")
                raise
    
    async def _enrich_place_details(self, places: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """장소 상세 정보 수집"""
        enriched_places = []
        for place in places:
            # LLM을 통한 장소 설명 생성
            description_prompt = ChatPromptTemplate.from_messages([
                SystemMessage(content="""당신은 여행 장소 설명 전문가입니다.
                주어진 장소에 대한 매력적인 설명을 작성해주세요.
                다음 정보를 포함해주세요:
                1. 장소의 주요 특징
                2. 방문하기 좋은 시간
                3. 주변 관광지
                4. 교통 정보
                5. 방문 팁"""),
                HumanMessage(content=f"장소: {place['name']}, 위치: {place['location']['address']}, 카테고리: {place['category']}")
            ])
            
            description_response = await self.llm.ainvoke(description_prompt.format_messages())
            
            enriched_place = {
                **place,
                "description": description_response.content,
                "details": {
                    "contact": place.get("contact", ""),
                    "website": place.get("link", ""),
                    "category": place.get("category", ""),
                    "coordinates": place["location"]["coordinates"],
                    "address": {
                        "street": place["location"]["road_address"],
                        "full": place["location"]["address"]
                    }
                }
            }
            enriched_places.append(enriched_place)
        
        return enriched_places
