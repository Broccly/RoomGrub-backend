from fastapi import APIRouter

router = APIRouter(prefix = "/api/v1/auth")


@router.post("/login")
def login(request):
  return

@router.get("/me")
def me(user):
  return user

@router.post("/logout")
def logout(request):
  return