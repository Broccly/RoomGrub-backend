from fastapi import FastAPI, Depends
from app.api.rooms.api import create_room_endpoint, get_room, list_rooms
from app.dependencies.current_user import get_current_user

app = FastAPI()

auth_required = [Depends(get_current_user)]

app.include_router(create_room_endpoint, dependencies=auth_required)
app.include_router(get_room)
app.include_router(list_rooms)

