from typing import Optional, Protocol, Union, runtime_checkable

from strawberry.asgi import Request, WebSocket

AppRequest = Union[Request, WebSocket]


@runtime_checkable
class AuthContext(Protocol):
    ...


class AppContext(Protocol):
    request: AppRequest
    auth: Optional[AuthContext] = None


__all__ = ["AppRequest", "AppContext", "AuthContext"]