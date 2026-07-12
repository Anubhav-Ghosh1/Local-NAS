from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from contextlib import asynccontextmanager

from config import settings
from auth import router as auth_router, init_users
from files_router import router as files_router
from stream_router import router as stream_router
from roots_router import router as roots_router
from logs_router import router as logs_router
from roots import init_roots


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_users()
    init_roots()
    yield


app = FastAPI(title="Home NAS", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router,  prefix="/api/auth",   tags=["auth"])
app.include_router(roots_router, prefix="/api/roots",  tags=["roots"])
app.include_router(files_router, prefix="/api/files",  tags=["files"])
app.include_router(stream_router,prefix="/api/stream", tags=["stream"])
app.include_router(logs_router,  prefix="/api/logs",   tags=["logs"])

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    return RedirectResponse(url="/static/index.html")
