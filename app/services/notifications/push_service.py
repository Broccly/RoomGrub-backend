import json
import logging
import firebase_admin
from firebase_admin import credentials, messaging
from sqlalchemy import Connection
from db.config import get_firebase_credentials_json
from app.models.notifications.notifications_model import (
    get_fcm_tokens_for_users,
    delete_fcm_tokens,
)

logger = logging.getLogger(__name__)

# FCM rejects these tokens permanently (app uninstalled, data cleared, other project).
_DEAD_TOKEN_ERRORS = (messaging.UnregisteredError, messaging.SenderIdMismatchError)

_app: firebase_admin.App | None = None
_init_attempted = False


def _get_app() -> firebase_admin.App | None:
    global _app, _init_attempted
    if _init_attempted:
        return _app
    _init_attempted = True
    raw = get_firebase_credentials_json()
    if not raw:
        logger.warning("FIREBASE_CREDENTIALS_JSON not set; push notifications disabled")
        return None
    try:
        _app = firebase_admin.initialize_app(credentials.Certificate(json.loads(raw)))
    except Exception:
        logger.exception("Failed to initialise Firebase; push notifications disabled")
    return _app


def send_push(conn: Connection, user_ids: list[int], title: str, body: str, data: dict[str, str]) -> None:
    """Best-effort push to every registered device of the given users. Never raises.

    Runs inside the caller's transaction, so its queries go in savepoints: in
    Postgres a failed statement aborts the whole transaction, which would
    silently roll back the caller's work (e.g. the expense) at commit.
    """
    try:
        if not user_ids:
            return
        with conn.begin_nested():
            tokens = get_fcm_tokens_for_users(conn, user_ids)
        if not tokens:
            return
        app = _get_app()
        if app is None:
            return

        messages = [
            messaging.Message(
                token=token,
                notification=messaging.Notification(title=title, body=body),
                data=data,
            )
            for token in tokens
        ]
        response = messaging.send_each(messages, app=app)

        dead = [
            token
            for token, result in zip(tokens, response.responses)
            if isinstance(result.exception, _DEAD_TOKEN_ERRORS)
        ]
        if dead:
            with conn.begin_nested():
                delete_fcm_tokens(conn, dead)
        if response.failure_count > len(dead):
            logger.warning("Push failed for %d token(s)", response.failure_count - len(dead))
    except Exception:
        logger.exception("Failed to send push notification %r", title)
