from __future__ import annotations

from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
user_id_var: ContextVar[str] = ContextVar("user_id", default="-")


def set_request_context(*, request_id: str, user_id: str = "-") -> tuple[object, object]:
    request_token = request_id_var.set(request_id)
    user_token = user_id_var.set(user_id)
    return request_token, user_token


def update_user_context(user_id: str) -> object:
    return user_id_var.set(user_id)


def reset_request_context(request_token: object, user_token: object) -> None:
    request_id_var.reset(request_token)
    user_id_var.reset(user_token)


def reset_user_context(token: object) -> None:
    user_id_var.reset(token)
