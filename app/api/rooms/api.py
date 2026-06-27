from fastapi import APIRouter, Query
from app.services.rooms.rooms_services import create_room

router = APIRouter(prefix = "/api/v1/rooms", tags = ["Rooms"])

@router.post("", status_code=201)
def create_room_endpoint(request, conn):
  result = create_room(request, conn)
  return result

@router.get("")
def list_rooms(request, conn):
  return

@router.get("/{room_id}")
def get_room(room_id, conn):
  return