"""
blog_app.core.protocols -- interfaces for inter-module communication 

"""

from datetime import datetime
from typing import (
    Awaitable,
    Hashable,
    List,
    Optional,
    Protocol,
    TypeVar,
    Union,
    runtime_checkable,
)
import strawberry

from strawberry.asgi import Request, WebSocket

from blog_app.core.result import Result
from blog_app.core.types import AppError
from blog_app.core.model import ReactionType
from blog_app.core.helpers import Collection

AppRequest = Union[Request, WebSocket]
KeyType = TypeVar("KeyType", contravariant=True, bound=Hashable)
LoaderType = TypeVar("LoaderType", covariant=True)


class Dataloader(Protocol[KeyType, LoaderType]):
    def load(self, key: KeyType) -> Awaitable[LoaderType]:
        ...


@strawberry.interface
class Person:
    id: strawberry.ID
    name: str


AppReactionType = strawberry.enum(ReactionType)


@strawberry.interface(name="Reaction")
class AppReaction:
    id: int
    comment_id: int
    reaction_type: AppReactionType
    author_id: strawberry.ID
    author: Person
    updated: datetime


@strawberry.interface(name="Comment")
class AppComment:
    id: int
    post_id: int
    content: str
    author_id: strawberry.ID
    author: Person
    reactions: Collection[AppReaction] = strawberry.field(
        description="Return all reactions which have been set on this comment,"
        " wrapped in a `Collection`."
    )
    created: datetime
    updated: datetime


@strawberry.interface(name="Post")
class AppPost:
    id: int
    author_id: strawberry.ID
    author: Person
    title: str
    content: str
    comments: Collection[AppComment] = strawberry.field(
        description="Return all comments which have been added to this post,"
        " wrapped in a `Collection`."
    )
    created: datetime
    updated: datetime


@runtime_checkable
class AuthContext(Protocol):
    @property
    def users(self) -> Dataloader[strawberry.ID, Optional[Person]]:
        ...

    async def get_logged_in_user(self) -> Result[Person, AppError]:
        ...


@runtime_checkable
class PostContext(Protocol):
    @property
    def dataloader(self) -> Dataloader[int, Optional[AppPost]]:
        ...


@runtime_checkable
class CommentContext(Protocol):
    @property
    def by_post_id(self) -> Dataloader[int, List[AppComment]]:
        ...


@runtime_checkable
class ReactionContext(Protocol):
    @property
    def by_comment_id(self) -> Dataloader[int, List[AppReaction]]:
        ...


class AppContext(Protocol):
    request: AppRequest
    auth: AuthContext
    posts: PostContext
    comments: CommentContext
    reactions: ReactionContext


__all__ = [
    "AppRequest",
    "AppContext",
    "AuthContext",
    "CommentContext",
    "PostContext",
    "ReactionContext",
    "Person",
    "AppPost",
    "AppComment",
    "AppReaction",
    "AppReactionType",
]
