import httpx
from fastapi import HTTPException


def _verify_google(token: str) -> dict:
    r = httpx.get(f"https://oauth2.googleapis.com/tokeninfo?id_token={token}")
    if r.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid Google token")
    data = r.json()
    if "error" in data:
        raise HTTPException(status_code=401, detail=f"Google token error: {data['error']}")
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
