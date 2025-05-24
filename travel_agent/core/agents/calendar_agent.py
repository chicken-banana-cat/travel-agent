from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build
import os
import json
from pathlib import Path

from langchain.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage

from ..config.settings import settings
from ...utils.cache_client import cache_client
from .base import BaseAgent


class CalendarAgent(BaseAgent):
    """캘린더 관리를 담당하는 에이전트"""

    def __init__(self):
        super().__init__(
            name="calendar_agent",
            description="여행 일정의 캘린더 관리를 담당하는 에이전트",
        )
        self.prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessage(
                    content="""당신은 캘린더 관리 전문가입니다.
            여행 일정을 캘린더에 등록하고 관리합니다.
            일정 충돌을 방지하고 효율적인 시간 관리를 도와주세요.
            
            다음 규칙을 따라주세요:
            1. 사용자와 대화를 통해 어떤 일정을 캘린더에 등록할지 결정합니다.
            2. 각 일정에 대해 사용자의 의견을 물어보고, 필요에 따라 수정을 제안합니다.
            3. 시간 충돌이나 비효율적인 일정 배치가 있다면 사용자에게 알려주세요.
            4. 사용자가 원하는 경우에만 일정을 등록하세요.
            5. 예약이 필요한 활동은 사용자에게 알려주세요."""
                ),
                HumanMessage(content="{action}"),
            ]
        )

        self.tips = []
        self.email = None

    async def validate(self, input_data: Dict[str, Any]) -> bool:
        """캘린더 작업 유효성 검증"""
        # if "action" not in input_data:
        #     return False
        #
        # if input_data["action"] == "register_itinerary":
        #     required_fields = ["itinerary"]
        #     return all(field in input_data for field in required_fields)
        #
        return True

    def _parse_duration(self, duration_str: str) -> int:
        """시간 문자열을 분 단위로 변환"""
        hours = 0
        minutes = 0

        if "시간" in duration_str:
            hours = int(duration_str.split("시간")[0])
            if "분" in duration_str:
                minutes = int(duration_str.split("시간")[1].split("분")[0])
        elif "분" in duration_str:
            minutes = int(duration_str.split("분")[0])

        return hours * 60 + minutes

    def _create_calendar_event(
        self, activity: Dict[str, Any], start_date: datetime, day: int
    ) -> Dict[str, Any]:
        """캘린더 이벤트 생성"""
        event_date = start_date + timedelta(days=day - 1)
        time_parts = activity["time"].split(":")
        event_datetime = event_date.replace(
            hour=int(time_parts[0]), minute=int(time_parts[1])
        )

        duration_minutes = self._parse_duration(activity["duration"])
        end_datetime = event_datetime + timedelta(minutes=duration_minutes)

        # 예약이 필요한 활동인지 확인
        requires_reservation = (
            "예약" in activity["activity"] or "사전 예약" in activity["activity"]
        )
        
        event = {
            "summary": activity["activity"],
            "location": activity["location"],
            "start": {"dateTime": event_datetime.isoformat(), "timeZone": "Asia/Seoul"},
            "end": {"dateTime": end_datetime.isoformat(), "timeZone": "Asia/Seoul"},
            "description": f"비용: {int(activity['cost']):,}원\n장소: {activity['location']}\n"
            + ("⚠️ 사전 예약이 필요한 활동입니다." if requires_reservation else ""),
        }
        
        # Google Calendar API 호출
        creds = self._get_credentials()
        service = build('calendar', 'v3', credentials=creds)
        created_event = service.events().insert(calendarId=self.email, body=event).execute()
        
        return created_event

    def _get_credentials(self) -> service_account.Credentials:
        """Google API 인증 정보를 가져옵니다."""
        info = {
            "type": "service_account",
            "project_id": "travel-agent-460815",
            "private_key_id": os.environ["GOOGLE_PRIVATE_KEY_ID"],
            "private_key": os.environ["GOOGLE_PRIVATE_KEY"].replace("\\n", "\n"),
            "client_email": "travel-agent-calendar@travel-agent-460815.iam.gserviceaccount.com",
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/travel-agent-calendar%40travel-agent-460815.iam.gserviceaccount.com",
            "universe_domain": "googleapis.com"
        }
        credentials = service_account.Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/calendar"]
        )
        return credentials

    def _get_relevant_tips(self, activity: Dict[str, Any]) -> List[str]:
        """활동과 관련된 팁 반환"""
        relevant_tips = []
        activity_lower = activity["activity"].lower()

        for tip in self.tips:
            tip_lower = tip.lower()
            if any(keyword in tip_lower for keyword in activity_lower.split()):
                relevant_tips.append(tip)

        return relevant_tips

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """캘린더 작업 처리"""
        if not await self.validate(input_data):
            return {
                "status": "error",
                "error": "Invalid calendar operation",
                "message": "필수 요구사항이 누락되었습니다.",
            }
        msg = input_data["context"]
        session_id = input_data["session_id"]
        session_data = cache_client.get_conversation_history(session_id)
        plan = session_data["plan"][-1]["data"]
        itinerary = plan["itinerary"]
        start_date = datetime.fromisoformat(plan["departure_date"])
        # 추천사항과 팁 저장
        init_conversation_state = {
            "current_day": None,
            "current_activity": None,
            "confirmed_events": [],
            "pending_events": [],
            "recommendations": None,
        }
        init_conversation_state["recommendations"] = plan.get("recommendations", [])
        self.tips = plan.get("tips", [])
        self.email = session_data["email"][-1]["data"]

        # 대화형 일정 등록 프로세스 시작
        if "conversation_state" not in session_data:
            # 첫 번째 일정 제안
            first_day = itinerary[0]
            first_activity = first_day["activities"][0]
            init_conversation_state["current_day"] = 1
            init_conversation_state["current_activity"] = 0

            # 관련 팁 확인
            relevant_tips = self._get_relevant_tips(first_activity)
            tips_message = (
                "\n\n관련 팁:\n" + "\n".join(f"- {tip}" for tip in relevant_tips)
                if relevant_tips
                else ""
            )
            cache_client.add_message(
                session_id,
                {"type": "conversation_state", "data": init_conversation_state},
            )
            return {
                "status": "conversation",
                "message": f"여행 첫날({first_day['day']}일차)의 첫 일정을 캘린더에 등록하시겠습니까? ({start_date})\n"
                f"시간: {first_activity['time']}\n"
                f"활동: {first_activity['activity']}\n"
                f"장소: {first_activity['location']}\n"
                f"소요시간: {first_activity['duration']}\n"
                f"비용: {int(first_activity['cost']):,}원"
                f"{tips_message}\n\n"
                f"등록하시려면 'yes', 건너뛰시려면 'skip', 종료하시려면 'done'을 입력해주세요.",
                "conversation_state": init_conversation_state,
            }

        # 사용자 응답 처리
        user_response = msg.lower()

        conversation_state = session_data["conversation_state"][-1]["data"]

        if user_response == "done":
            cache_client.clear_conversation(session_id)
            return {
                "status": "success",
                "operation": "register_itinerary",
                "events": conversation_state["confirmed_events"],
                "message": f"총 {len(conversation_state['confirmed_events'])}개의 일정이 캘린더에 등록되었습니다.",
            }

        current_day = int(conversation_state["current_day"])
        current_activity = int(conversation_state["current_activity"])

        if user_response == "yes":
            activity = itinerary[current_day - 1]["activities"][current_activity]
            event = self._create_calendar_event(activity, start_date, current_day)

            # TODO 시간 충돌 확인
            conversation_state["confirmed_events"].append(event)

        # 다음 일정으로 이동
        current_activity += 1
        if current_activity >= len(itinerary[current_day - 1]["activities"]):
            current_day += 1
            current_activity = 0

            if current_day > len(itinerary):
                return {
                    "status": "success",
                    "operation": "register_itinerary",
                    "events": conversation_state["confirmed_events"],
                    "message": f"총 {len(conversation_state['confirmed_events'])}개의 일정이 캘린더에 등록되었습니다.",
                }

        conversation_state["current_day"] = current_day
        conversation_state["current_activity"] = current_activity

        next_activity = itinerary[current_day - 1]["activities"][current_activity]
        relevant_tips = self._get_relevant_tips(next_activity)
        tips_message = (
            "\n\n관련 팁:\n" + "\n".join(f"- {tip}" for tip in relevant_tips)
            if relevant_tips
            else ""
        )
        cache_client.add_message(
            session_id, {"type": "conversation_state", "data": conversation_state}
        )
        return {
            "status": "conversation",
            "message": f"{current_day}일차의 다음 일정을 캘린더에 등록하시겠습니까?\n"
            f"시간: {next_activity['time']}\n"
            f"활동: {next_activity['activity']}\n"
            f"장소: {next_activity['location']}\n"
            f"소요시간: {next_activity['duration']}\n"
            f"비용: {int(next_activity['cost']):,}원"
            f"{tips_message}\n\n"
            f"등록하시려면 'yes', 건너뛰시려면 'skip', 종료하시려면 'done'을 입력해주세요.",
            "conversation_state": conversation_state,
        }
