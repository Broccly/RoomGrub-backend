from fastapi import APIRouter, Depends, status
from sqlalchemy import Connection
from db.engine import db_conn
from app.dependencies.room_access import require_room_admin, require_room_member
from app.api.splits.schemas import SplitsData, SettleAllRequest
from app.services.splits import splits_services

router = APIRouter(prefix="/api/v1/rooms", tags=["Splits"])


@router.get("/{room_id}/splits", response_model=SplitsData)
def get_splits(
    room_id: int,
    conn: Connection = Depends(db_conn),
    membership: dict = Depends(require_room_member),
) -> SplitsData:
    return splits_services.get_splits_data(conn, room_id)


@router.post("/{room_id}/splits/settle-all", status_code=status.HTTP_204_NO_CONTENT)
def settle_all(
    room_id: int,
    body: SettleAllRequest,
    conn: Connection = Depends(db_conn),
    membership: dict = Depends(require_room_admin),
) -> None:
    splits_services.settle_all(conn, room_id, [m.model_dump() for m in body.members])
