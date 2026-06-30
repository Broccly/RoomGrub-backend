from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import Connection
from db.engine import db_conn
from app.dependencies.current_user import get_current_user
from app.dependencies.room_access import require_room_admin
from app.api.expenses.schemas import (
    ExpenseCreate,
    ExpenseForMemberCreate,
    ExpenseUpdate,
    ExpenseResponse,
    PaginatedExpenses,
)
from app.services.expenses import expenses_services

router = APIRouter(prefix="/api/v1/rooms", tags=["Expenses"])


@router.get("/{room_id}/expenses", response_model=PaginatedExpenses)
def list_expenses(
    room_id: int,
    cursor: int | None = Query(default=None),
    limit: int = Query(default=20, le=100),
    settled: bool | None = Query(default=None),
    search: str | None = Query(default=None),
    user_email: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    conn: Connection = Depends(db_conn),
    current_user: dict = Depends(get_current_user),
):
    return expenses_services.list_expenses(
        conn, room_id, cursor=cursor, limit=limit,
        settled=settled, search=search, user_email=user_email,
        date_from=date_from, date_to=date_to,
    )


@router.post("/{room_id}/expenses", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
def add_expense(
    room_id: int,
    body: ExpenseCreate,
    conn: Connection = Depends(db_conn),
    current_user: dict = Depends(get_current_user),
):
    return expenses_services.add_expense(conn, room_id, body.material, body.money, current_user, body.created_at)


@router.patch("/{room_id}/expenses/{expense_id}", response_model=ExpenseResponse)
def edit_expense(
    room_id: int,
    expense_id: int,
    body: ExpenseUpdate,
    conn: Connection = Depends(db_conn),
    membership: dict = Depends(require_room_admin),
):
    return expenses_services.edit_expense(
        conn, room_id, expense_id,
        body.material, body.money, body.created_at,
        membership["user"],
    )


@router.delete("/{room_id}/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(
    room_id: int,
    expense_id: int,
    conn: Connection = Depends(db_conn),
    membership: dict = Depends(require_room_admin),
):
    expenses_services.remove_expense(conn, room_id, expense_id, membership["user"])
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{room_id}/expenses/for-member",
    response_model=ExpenseResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_expense_for_member(
    room_id: int,
    body: ExpenseForMemberCreate,
    conn: Connection = Depends(db_conn),
    membership: dict = Depends(require_room_admin),
):
    return expenses_services.add_expense_for_member(
        conn, room_id, body.material, body.money, body.user_email, body.created_at
    )
