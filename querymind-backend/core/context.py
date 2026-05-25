from contextvars import ContextVar
from uuid import uuid4

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
session_id_var: ContextVar[str] = ContextVar("session_id", default="-")


def get_request_id() -> str:
    return request_id_var.get()


def set_request_id(rid: str) -> None:
    request_id_var.set(rid)


def get_session_id() -> str:
    return session_id_var.get()


def set_session_id(sid: str) -> None:
    session_id_var.set(sid)


def generate_request_id() -> str:
    return str(uuid4())
