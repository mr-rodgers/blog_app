import re
from typing import List, NewType, Optional
from datetime import datetime

import strawberry
from strawberry.types import Info

from blog_app.core import AppComment, AppContext, AppRequest, Person, AppPost
from blog_app.core.helpers import Collection


WHITESPACE_REGEX = re.compile(r"\s+")


def parse_title(title: str):
    """
    Collapse whitespace within a string and trim both ends.

    If the string is empty afterward, a ValueError will be raised.
    (since this function is intended to be used as a scalar; strawberry
    will convert the value error into a validation error on the field)
    """
    fixed = WHITESPACE_REGEX.sub(" ", title.strip())

    if fixed:
        return fixed
    else:
        raise ValueError("PostTitle cannot contain only whitespace.")


PostTitle = strawberry.scalar(
    NewType("PostTitle", str),
    description="A post title, within which all whitespace is collapsed: e.g. '  foo    bar   ' -> 'foo bar'",
    parse_value=parse_title,
)


@strawberry.type(name="Post_")
class Post(AppPost):
    id: int
    author_id: strawberry.ID
    title: str
    content: str
    created: datetime
    updated: datetime

    @strawberry.field
    async def author(self, info: Info[AppContext, AppRequest]) -> Person:
        # ignore type error because we don't expect this to resolve
        # null; this should trigger a low-level gql error instead if this does
        # happen.
        return await info.context.auth.users.load(self.author_id)  # type: ignore

    @strawberry.field
    async def comments(
        self, info: Info[AppContext, AppRequest]
    ) -> Collection[AppComment]:
        return Collection(lambda: info.context.comments.by_post_id.load(self.id))


@strawberry.type
class PostRetrievalError:
    message: str


@strawberry.type
class PostCreationResponse:
    id: int
    title: PostTitle  # type: ignore[valid-type]


@strawberry.type
class PostUpdateResponse:
    id: int
    title: Optional[PostTitle] = None  # type: ignore[valid-type]
    content: Optional[str] = None


@strawberry.type
class PostDeletionResponse:
    id: int
