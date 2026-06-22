from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.database import Base, engine
from backend.app.routers import auth, user_status
from backend.app.models import models

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


@app.get("/")
def root():
    return {"message": "Nudge API running"}