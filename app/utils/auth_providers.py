import httpx
from fastapi import HTTPException
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from db.config import get_google_client_id

_GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")
_google_request = google_requests.Request()


def _verify_google(token: str) -> dict:
    try:
        data = google_id_token.verify_oauth2_token(token, _google_request, get_google_client_id())
    except ValueError as e:
        raise HTTPException(status_code=401, detail=f"Invalid Google token: {e}")

    if data.get("iss") not in _GOOGLE_ISSUERS:
        raise HTTPException(status_code=401, detail="Invalid Google token issuer")

    email = data.get("email")
    if not email:
        raise HTTPException(status_code=401, detail="Google token missing email")
    return {
        "email": email,
        "name": data.get("name"),
        "picture": data.get("picture"),
    }


def _verify_facebook(token: str) -> dict:
    r = httpx.get(
        "https://graph.facebook.com/me",
        params={"access_token": token, "fields": "id,name,email,picture"},
    )
    if r.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid Facebook token")
    data = r.json()
    if "error" in data:
        raise HTTPException(status_code=401, detail=f"Facebook token error: {data['error']['message']}")
    email = data.get("email")
    if not email:
        raise HTTPException(
            status_code=401,
            detail="Facebook token missing email. Ensure email permission is granted.",
        )
    picture = None
    if isinstance(data.get("picture"), dict):
        picture = data["picture"].get("data", {}).get("url")
    return {
        "email": email,
        "name": data.get("name"),
        "picture": picture,
    }


_PROVIDERS = {
    "google": _verify_google,
    "facebook": _verify_facebook,
}


def verify_provider_token(provider: str, token: str) -> dict:
    fn = _PROVIDERS.get(provider.lower())
    if not fn:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown provider '{provider}'. Supported: {', '.join(_PROVIDERS)}",
        )
    return fn(token)
