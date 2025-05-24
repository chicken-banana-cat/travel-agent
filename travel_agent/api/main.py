from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import chat

app = FastAPI(
    title="Travel Agent API",
    description="여행 일정 계획 멀티 에이전트 API",
    version="0.1.0",
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 실제 운영 환경에서는 특정 도메인만 허용하도록 수정
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(chat.router, tags=["chat"])


@app.get("/")
async def root():
    """API 상태 확인 엔드포인트"""
    return {"status": "ok", "message": "Travel Agent API is running"}
