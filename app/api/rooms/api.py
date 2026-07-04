from fastapi import APIRouter, Depends, status
from sqlalchemy import Connection
from db.engine import db_conn
from app.dependencies.current_user import get_current_user
from app.dependencies.room_access import require_room_admin
from app.api.rooms.schemas import RoomResponse, RoomSummary, DashboardResponse
from app.services.rooms import rooms_services

router = APIRouter(prefix="/api/v1/rooms", tags=["Rooms"])


@router.get("", response_model=list[RoomResponse])
def list_rooms(
    conn: Connection = Depends(db_conn),
    current_user: dict = Depends(get_current_user),
):
    return rooms_services.list_rooms(conn, current_user)


@router.post("", response_model=RoomResponse, status_code=status.HTTP_201_CREATED)
def create_room(
    conn: Connection = Depends(db_conn),
    current_user: dict = Depends(get_current_user),
):
    return rooms_services.create_room(conn, current_user=current_user)


@router.get("/{room_id}", response_model=RoomSummary)
def get_room_summary(
    room_id: int,
    conn: Connection = Depends(db_conn),
    current_user: dict = Depends(get_current_user),
):
    return rooms_services.get_room_summary(conn, room_id)


@router.get("/{room_id}/dashboard", response_model=DashboardResponse)
def get_room_dashboard(
    room_id: int,
    conn: Connection = Depends(db_conn),
    current_user: dict = Depends(get_current_user),
):
    return rooms_services.get_room_dashboard(conn, room_id)


@router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_room(
    room_id: int,
    conn: Connection = Depends(db_conn),
    membership: dict = Depends(require_room_admin),
):
    rooms_services.delete_room(conn, room_id)
