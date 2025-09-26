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
    task = getattr(app.state, "heartbeat_task", None)
    if task:
        task.cancel()


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
