import logging
import asyncio
from fastapi import FastAPI
from app.config import settings
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger("uvicorn.error")

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def start_heartbeat():
    app.state.heartbeat_task = asyncio.create_task(heartbeat())

@app.on_event("shutdown")
async def stop_heartbeat():
    app.state.heartbeat_task.cancel()

async def heartbeat():
    while True:
        logger.info("Heartbeat: server is running")
        await asyncio.sleep(60)  # 60초마다 로그

@app.get("/health", tags=["system"])
async def health_check() -> dict[str, str]:
    logger.info("Health check endpoint called")
    return {"status": "ok"}
