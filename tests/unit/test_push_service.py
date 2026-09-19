from contextlib import nullcontext
from types import SimpleNamespace

from firebase_admin import messaging

from app.services.notifications import push_service


def _patch(monkeypatch, tokens, send_each):
    deleted: list[list[str]] = []
    monkeypatch.setattr(push_service, "get_fcm_tokens_for_users", lambda conn, user_ids: tokens)
    monkeypatch.setattr(push_service, "delete_fcm_tokens", lambda conn, t: deleted.append(t))
    monkeypatch.setattr(push_service, "_get_app", lambda: object())
    monkeypatch.setattr(push_service.messaging, "send_each", send_each)
    return deleted


# send_push wraps its queries in savepoints; a no-op context stands in for them.
FAKE_CONN = SimpleNamespace(begin_nested=nullcontext)


def _response(*exceptions):
    responses = [SimpleNamespace(exception=e) for e in exceptions]
    return SimpleNamespace(responses=responses, failure_count=sum(e is not None for e in exceptions))


class TestSendPush:
    def test_sends_one_message_per_token(self, monkeypatch):
        sent = []

        def send_each(messages, app):
            sent.extend(messages)
            return _response(None, None)

        _patch(monkeypatch, ["tok-a", "tok-b"], send_each)
        push_service.send_push(FAKE_CONN, [1, 2], "title", "body", {"type": "t"})

        assert [m.token for m in sent] == ["tok-a", "tok-b"]
        assert sent[0].notification.title == "title"
        assert sent[0].data == {"type": "t"}

    def test_prunes_unregistered_tokens_only(self, monkeypatch):
        dead = messaging.UnregisteredError("gone")
        other = messaging.QuotaExceededError("slow down")
        deleted = _patch(monkeypatch, ["dead", "ok", "busy"], lambda messages, app: _response(dead, None, other))

        push_service.send_push(FAKE_CONN, [1], "t", "b", {})

        assert deleted == [["dead"]]

    def test_no_tokens_skips_firebase(self, monkeypatch):
        def send_each(messages, app):
            raise AssertionError("should not send")

        _patch(monkeypatch, [], send_each)
        push_service.send_push(FAKE_CONN, [1], "t", "b", {})

    def test_never_raises(self, monkeypatch):
        def send_each(messages, app):
            raise RuntimeError("network down")

        _patch(monkeypatch, ["tok"], send_each)
        push_service.send_push(FAKE_CONN, [1], "t", "b", {})
