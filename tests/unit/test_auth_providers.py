import pytest
from fastapi import HTTPException

from app.utils import auth_providers


class TestVerifyGoogle:
    def test_valid_token_returns_user_info(self, monkeypatch):
        monkeypatch.setattr(
            auth_providers.google_id_token,
            "verify_oauth2_token",
            lambda token, request, client_id: {
                "iss": "https://accounts.google.com",
                "email": "user@example.com",
                "name": "Some User",
                "picture": "https://example.com/p.png",
            },
        )

        result = auth_providers._verify_google("valid-token")

        assert result == {
            "email": "user@example.com",
            "name": "Some User",
            "picture": "https://example.com/p.png",
        }

    def test_invalid_signature_or_audience_raises_401(self, monkeypatch):
        def _raise(token, request, client_id):
            raise ValueError("Wrong audience")

        monkeypatch.setattr(auth_providers.google_id_token, "verify_oauth2_token", _raise)

        with pytest.raises(HTTPException) as exc_info:
            auth_providers._verify_google("bad-token")
        assert exc_info.value.status_code == 401

    def test_wrong_issuer_raises_401(self, monkeypatch):
        monkeypatch.setattr(
            auth_providers.google_id_token,
            "verify_oauth2_token",
            lambda token, request, client_id: {
                "iss": "https://evil.example.com",
                "email": "user@example.com",
            },
        )

        with pytest.raises(HTTPException) as exc_info:
            auth_providers._verify_google("token")
        assert exc_info.value.status_code == 401

    def test_missing_email_raises_401(self, monkeypatch):
        monkeypatch.setattr(
            auth_providers.google_id_token,
            "verify_oauth2_token",
            lambda token, request, client_id: {"iss": "accounts.google.com"},
        )

        with pytest.raises(HTTPException) as exc_info:
            auth_providers._verify_google("token")
        assert exc_info.value.status_code == 401
