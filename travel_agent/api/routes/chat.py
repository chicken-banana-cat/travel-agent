from typing import AsyncGenerator, Dict, Any, List
import json
import traceback
import logging

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from travel_agent.core.agents.orchestrator import Orchestrator

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()
orchestrator = Orchestrator()

# 세션별 대화 히스토리 저장
conversation_history: Dict[str, List[Dict]] = {}


class ChatRequest(BaseModel):
    """채팅 요청 모델"""
    message: str
    session_id: str


class ChatResponse(BaseModel):
    """채팅 응답 모델"""
    content: str
    status: str
    metadata: Dict[str, Any] = {}


async def stream_response(message: str, session_id: str = None) -> AsyncGenerator[str, None]:
    """스트리밍 응답 생성기"""
    try:
        # 현재 세션의 컨텍스트와 이전 결과 가져오기
        session_data = conversation_history.get(session_id, {})
        context = session_data.get("context", {})
        previous_result = session_data.get("previous_result", None)
        
        # Orchestrator를 통해 메시지 처리
        async for chunk in orchestrator.process_stream({
            "message": message,
            "context": context,
            "previous_result": previous_result,
            "plan": session_data.get("plan", None)
        }):
            if chunk["status"] in ["success", 'need_more_info']:
                yield f"data: {json.dumps(chunk['result'])}\n\n"
                
                # 컨텍스트와 이전 결과 업데이트
                if session_id:
                    if session_id not in conversation_history:
                        conversation_history[session_id] = {}
                    if 'current_context' in chunk["result"]:
                        conversation_history[session_id]["context"] = chunk["result"]['current_context']
                    if chunk["status"] == "success":
                        result = chunk["result"]

                        if plan := result.get("plan"):
                            conversation_history[session_id]["plan"] = plan
                        else:
                            conversation_history[session_id]["previous_result"] = chunk["result"]
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
        error_data = {
            "error": str(e),
            "stacktrace": traceback.format_exc()
        }
        yield f"event: error\ndata: {json.dumps(error_data)}\n\n"
        yield "event: complete\ndata: {}\n\n"

#
# @router.post("/chat")
# async def chat(request: ChatRequest) -> StreamingResponse:
#     """채팅 엔드포인트"""
#     try:
#         # 현재 세션의 대화 히스토리 가져오기
#         messages = conversation_history.get(request.session_id, [])
#
#         async def generate():
#             async for chunk in orchestrator.process_stream({
#                 "message": request.message,
#                 "messages": messages
#             }):
#                 if chunk["status"] in ["success", "need_more_info"]:
#                     # 응답에 메시지 히스토리 포함
#                     yield f"data: {json.dumps(chunk['result'])}\n\n"
#
#                     # 대화 히스토리 업데이트
#                     if "messages" in chunk:
#                         conversation_history[request.session_id] = chunk["messages"]
#                 else:
#                     yield f"data: {json.dumps({'error': 'Failed to process message'})}\n\n"
#
#         return StreamingResponse(
#             generate(),
#             media_type="text/event-stream"
#         )
#     except Exception as e:
#         logging.error(f"Error in chat endpoint: {str(e)}")
#         logging.error(traceback.format_exc())
#         raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat")
async def chat(message: str, session_id: str = None) -> StreamingResponse:
    """채팅 엔드포인트 (SSE)"""
    try:
        return StreamingResponse(
            stream_response(message, session_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
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