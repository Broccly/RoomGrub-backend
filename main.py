from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth.api import router as auth_router
from app.api.rooms.api import router as rooms_router
from app.api.expenses.api import router as expenses_router
from app.api.members.api import router as members_router
from app.api.splits.api import router as splits_router
from app.api.invites.api import router as invites_router
from app.api.notifications.api import router as notifications_router

app = FastAPI(title="RoomGrub API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://roomgrub.app",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(rooms_router)
app.include_router(expenses_router)
app.include_router(members_router)
app.include_router(splits_router)
app.include_router(invites_router)
app.include_router(notifications_router)


@app.get("/health")
def health():
    return {"status": "ok"}
