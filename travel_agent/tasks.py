import asyncio
import logging
from pathlib import Path

from celery import Celery
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# 환경변수 설정을 먼저 수행
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

from travel_agent.core.agents.mail_agent import MailAgent
from travel_agent.core.agents.search_agent import SearchAgent
from travel_agent.core.config.settings import settings

# Celery app 초기화
celery_app = Celery("travel_agent")

# Celery 설정
celery_app.conf.update(
    broker_url=f"sqs://sqs.{settings.AWS_REGION}.amazonaws.com/{settings.AWS_ACCOUNT_ID}/travel-agent-queue",
    result_backend=None,
    broker_transport_options={
        "region": settings.AWS_REGION,
        "visibility_timeout": 3600,
        "polling_interval": 1,
    },
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Seoul",
    enable_utc=True,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)


@celery_app.task(name="process_search_and_mail")
def process_search_and_mail(context: dict, email: str, plan: dict):
    try:
        search_agent = SearchAgent()
        mail_agent = MailAgent()

        loop = asyncio.get_event_loop()

        search_result = loop.run_until_complete(
            search_agent.process({"plan": plan, "context": context})
        )

        loop.run_until_complete(
            mail_agent.process(
                {
                    "email": email,
                    "context": context,
                    "plan": plan,
                    "search_result": search_result,
                }
            )
        )

        return
    except Exception as e:
        logger.error(f"Task failed with error: {str(e)}", exc_info=True)
        raise e
