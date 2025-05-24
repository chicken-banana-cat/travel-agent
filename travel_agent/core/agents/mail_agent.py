import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict

from jinja2 import Template

from ..config.settings import settings
from .base import BaseAgent


class MailAgent(BaseAgent):
    """여행 계획 메일 전송을 담당하는 에이전트"""

    def __init__(self):
        super().__init__(
            name="mail_agent", description="여행 계획 메일 전송을 담당하는 에이전트"
        )
        self.smtp_server = settings.SMTP_SERVER
        self.smtp_port = settings.SMTP_PORT
        self.smtp_username = settings.SMTP_USERNAME
        self.smtp_password = settings.SMTP_PASSWORD
        self.sender_email = settings.SENDER_EMAIL

        # 이메일 템플릿 로드
        template_path = (
            Path(__file__).parent.parent / "templates" / "email_template.html"
        )
        with open(template_path, "r", encoding="utf-8") as f:
            self.email_template = Template(f.read())

    async def validate(self, input_data: Dict[str, Any]) -> bool:
        """메일 전송 요구사항 유효성 검증"""
        required_fields = []
        return all(field in input_data for field in required_fields)

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """메일 전송 처리"""
        if not await self.validate(input_data):
            return {
                "status": "error",
                "error": "Invalid mail requirements",
                "message": "필수 요구사항(email, plan, search_results)이 누락되었습니다.",
            }

        try:
            plan = input_data["plan"]
            search_result = input_data["search_result"]
            search_result["places"] = search_result["context"]["preferences"]["places"]

            destination = input_data["context"]["destination"]
            duration = input_data["context"]["duration"]
            itinerary = plan["itinerary"]
            budget = plan["budget"]
            recommendations = plan["recommendations"]
            tips = plan["tips"]
            places = search_result["places"]
            # 이메일 내용 생성
            email_content = self.email_template.render(
                destination=destination,
                duration=duration,
                itinerary=itinerary,
                budget=budget,
                recommendations=recommendations,
                tips=tips,
                places=[
                    {
                        "name": place["name"],
                        "description": place["description"],
                        "location": {"address": place["location"].get("address", "")},
                        "contact": place.get("contact", ""),
                        "link": place.get("link", ""),
                    }
                    for place in places
                ],
            )

            # 이메일 메시지 생성
            msg = MIMEMultipart()
            msg["Subject"] = f"[여행 계획] {destination} 여행 계획"
            msg["From"] = self.sender_email
            msg["To"] = input_data["email"]

            # HTML 내용 추가
            msg.attach(MIMEText(email_content, "html"))

            # 이메일 전송
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)

            return {
                "status": "success",
                "message": "여행 계획이 이메일로 전송되었습니다.",
                "email": input_data["message"],
            }

        except Exception as e:
            return {
                "status": "error",
                "error": "Mail sending failed",
                "message": f"이메일 전송 중 오류가 발생했습니다: {str(e)}",
            }
