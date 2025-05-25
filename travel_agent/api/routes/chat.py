import json
import logging
import traceback
from typing import Any, AsyncGenerator, Dict

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from travel_agent.core.agents.orchestrator import Orchestrator
from travel_agent.utils.cache_client import cache_client, convert_floats_to_int


# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()
orchestrator = Orchestrator()


class ChatRequest(BaseModel):
    """채팅 요청 모델"""

    message: str
    session_id: str


class ChatResponse(BaseModel):
    """채팅 응답 모델"""

    content: str
    status: str
    metadata: Dict[str, Any] = {}


async def stream_response(
    message: str, session_id: str = None
) -> AsyncGenerator[str, None]:
    """스트리밍 응답 생성기"""
    try:
        # 현재 세션의 컨텍스트와 이전 결과 가져오기
        session_data = (
            cache_client.get_conversation_history(session_id) if session_id else {}
        )
        context = session_data.get("context", {})
        results = session_data.get("results", None)

        # Orchestrator를 통해 메시지 처리
        async for chunk in orchestrator.process_stream(
            {
                "message": message,
                "context": context,
                "plan": session_data.get("plan", None),
                "session_id": session_id,
            }
        ):
            if chunk["status"] in ["success", "need_more_info"]:
                res = convert_floats_to_int(chunk['result'])
                yield f"data: {json.dumps(res)}\n\n"

                # 컨텍스트와 이전 결과 업데이트
                if session_id:
                    if "current_context" in chunk["result"]:
                        context = chunk["result"]["current_context"]
                    if chunk["status"] == "success":
                        result = chunk["result"]

                        if plan := result.get("plan"):
                            cache_client.add_message(
                                session_id, {"type": "plan", "data": plan}
                            )
                        else:
                            if r := results:
                                if r[-1] != chunk["result"]:
                                    r.append(chunk["result"])
                            else:
                                results = [chunk["result"]]

                            cache_client.add_message(
                                session_id, {"type": "result", "data": chunk["result"]}
                            )
            elif chunk["status"] == "processing":
                if msg := chunk.get("output_message"):
                    yield f"data: {json.dumps({'status': 'success', 'message': msg})}\n\n"
                continue
            else:
                yield f"data: {json.dumps({'error': 'Failed to process message'})}\n\n"

        # 스트림 완료를 알리는 이벤트 전송
        yield "event: complete\ndata: {}\n\n"

    except Exception as e:
        # 에러 로깅
        error_msg = f"Error in stream_response: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)

        # 에러 발생 시 에러 이벤트 전송
        error_data = {"error": str(e), "stacktrace": traceback.format_exc()}
        yield f"event: error\ndata: {json.dumps(error_data)}\n\n"
        yield "event: complete\ndata: {}\n\n"


@router.delete("/chat/{user_id}")
async def clear_chat(user_id: str):
    try:
        cache_client.clear_conversation(user_id)
        return {"status": "success", "message": "대화 기록이 삭제되었습니다."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/travel-agent")
async def chat(message: str, session_id: str = None) -> StreamingResponse:
    """채팅 엔드포인트 (SSE)"""
    try:
        return StreamingResponse(
            stream_response(message, session_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
