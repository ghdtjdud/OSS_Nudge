import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dotenv import load_dotenv

from backend.app.database import Base, engine
from backend.app.routers import (
    auth,
    chat,
    user_status,
    missions,
    dev_chat,
)
from backend.app.models import models

load_dotenv()

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Nudge API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(user_status.router)
app.include_router(chat.router)
app.include_router(missions.router)

if (
    os.getenv(
        "DEV_CHAT_ENABLED",
        "false",
    )
    .strip()
    .lower()
    == "true"
):
    app.include_router(
        dev_chat.router
    )


@app.get("/")
def root():
    return {"message": "Nudge API running"}