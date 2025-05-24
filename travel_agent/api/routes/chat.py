import json
import logging
import traceback
from typing import Any, AsyncGenerator, Dict, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from travel_agent.core.agents.orchestrator import Orchestrator

from ...utils.cache_client import cache_client

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
                yield f"data: {json.dumps(chunk['result'])}\n\n"

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


@router.post("/chat")
async def chat(user_id: str, message: str):
    try:
        # 캐시에서 대화 기록 가져오기
        messages = cache_client.get_conversation_history(user_id)

        # 새 메시지 추가
        new_message = {"role": "user", "content": message}
        cache_client.add_message(user_id, new_message)
        messages.append(new_message)

        # 여기에 에이전트 처리 로직 추가
        # ...

        return {"status": "success", "messages": messages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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


#
# @router.websocket("/ws/chat")
# async def websocket_endpoint(websocket: WebSocket):
#     await websocket.accept()
#
#     # 세션 ID 생성 (실제로는 더 안전한 방법 사용 필요)
#     session_id = str(id(websocket))
#     conversation_history[session_id] = []
#
#     try:
#         while True:
#             # 메시지 수신
#             message = await websocket.receive_text()
#
#             # 현재 세션의 대화 히스토리 가져오기
#             messages = conversation_history[session_id]
#
#             # 메시지 처리 및 스트리밍
#             async for chunk in orchestrator.process_stream({
#                 "message": message,
#                 "messages": messages
#             }):
#                 if chunk["status"] in ["success", "need_more_info"]:
#                     # 응답에 메시지 히스토리 포함
#                     yield f"data: {json.dumps(chunk['result'])}\n\n"
#
#                     # 대화 히스토리 업데이트
#                     if "messages" in chunk:
#                         conversation_history[session_id] = chunk["messages"]
#                 else:
#                     yield f"data: {json.dumps({'error': 'Failed to process message'})}\n\n"
#
#     except WebSocketDisconnect:
#         # 연결 종료 시 세션 정리
#         if session_id in conversation_history:
#             del conversation_history[session_id]
