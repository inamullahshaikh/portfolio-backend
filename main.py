"""Portfolio API — FastAPI + Motor + JWT admin + Gmail contact notifications."""

from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

_backend_root = Path(__file__).resolve().parent
# Parent first, then backend — later load wins for duplicate keys.
load_dotenv(_backend_root.parent / ".env")
load_dotenv(_backend_root / ".env", override=True)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db import close_db, connect_db, get_settings
from routes.admin import router as admin_router
from routes.public import router as public_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    yield
    await close_db()


app = FastAPI(title="Portfolio API", lifespan=lifespan)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(public_router)
app.include_router(admin_router)
