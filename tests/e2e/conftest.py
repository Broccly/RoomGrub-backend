from typing import Generator

import pytest
import httpx
from fastapi.testclient import TestClient

from app.utils.jwt_utils import create_jwt
from main import app

BASE_URL = "http://localhost:8000"

E2E_TEST_USER = dict(
  id = 23,
  email = "developersankar14@gmail.com",
  name = "E2E Test User",
  picture = None
)

def _auth_headers() -> dict[str, str]:
  token = create_jwt(E2E_TEST_USER)
  return {"Authorization": f"Bearer {token}"}

@pytest.fixture(scope="session")
def test_client() -> TestClient:
  return TestClient(app)

@pytest.fixture(scope="session")
def authed_client() -> Generator[httpx.Client, None, None]:
  with httpx.Client(base_url = BASE_URL, headers = _auth_headers()) as client:
    yield client