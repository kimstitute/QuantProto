import asyncio
import logging

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.models.symbol import Symbol
from app.schemas import SymbolCreate, SymbolRead
# 라우터 경로 가져오기
from .api import market, orders, ws
from .api import portfolio, trading, llm_trading
from .services.kis_auth import kis_auth
from .services.market_data_service import market_data_service
from .services.trading_engine import trading_engine

logger = logging.getLogger("uvicorn.error")

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:4173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(market.router)
app.include_router(ws.router)
app.include_router(orders.router)
app.include_router(portfolio.router)
app.include_router(trading.router)
app.include_router(llm_trading.router)


@app.on_event("startup")
async def start_heartbeat():
    # 하트비트 태스크 시작
    app.state.heartbeat_task = asyncio.create_task(heartbeat())
    
    # 트레이딩 엔진 시작 (스톱로스 모니터링)
    app.state.trading_engine_task = asyncio.create_task(trading_engine.start_monitoring())
    logger.info("트레이딩 엔진 모니터링 시작")
    
    # 한국투자증권 API 인증
    try:
        auth_result = kis_auth.auth()
        if auth_result:
            logger.info("한국투자증권 API 인증 성공")
        else:
            logger.warning("한국투자증권 API 인증 실패")
    except Exception as e:
        logger.error(f"한국투자증권 API 인증 오류: {e}")


@app.on_event("shutdown")
async def stop_heartbeat():
    # 트레이딩 엔진 종료
    trading_engine.stop_monitoring()
    trading_task = getattr(app.state, "trading_engine_task", None)
    if trading_task:
        trading_task.cancel()
        try:
            await trading_task
        except asyncio.CancelledError:
            pass
    logger.info("트레이딩 엔진 종료 완료")
    
    # 하트비트 태스크 종료
    task = getattr(app.state, "heartbeat_task", None)
    if task:
        task.cancel()
    
    # WebSocket 연결 종료
    try:
        await market_data_service.close_all_connections()
        logger.info("모든 WebSocket 연결 종료")
    except Exception as e:
        logger.error(f"WebSocket 연결 종료 오류: {e}")


def log_db_ready(db: Session) -> None:
    db.execute(text("SELECT 1"))


async def heartbeat():
    while True:
        logger.info("Heartbeat: server is running")
        await asyncio.sleep(60)


@app.get("/health", tags=["system"])
async def health_check() -> dict[str, str]:
    logger.info("Health check endpoint called")
    return {"status": "ok"}


@app.get("/db-test", tags=["system"])
def db_test(db: Session = Depends(get_db)) -> dict[str, str]:
    log_db_ready(db)
    return {"db": "ok"}


@app.post("/symbols", response_model=SymbolRead)
def create_symbol(payload: SymbolCreate, db: Session = Depends(get_db)) -> SymbolRead:
    symbol = Symbol(code=payload.code, name=payload.name)
    db.add(symbol)
    db.commit()
    db.refresh(symbol)
    return symbol


@app.get("/symbols", response_model=list[SymbolRead])
def list_symbols(db: Session = Depends(get_db)) -> list[SymbolRead]:
    symbols = db.query(Symbol).order_by(Symbol.id).all()
    return symbols
