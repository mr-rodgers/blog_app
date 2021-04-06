from typing import Optional

import strawberry


@strawberry.type
class PostUpdatedEvent:
    id: int
    title: Optional[str] = None
    content: Optional[str] = None


@strawberry.type
class PostDeletedEvent:
    id: int


@strawberry.type
class CommentAddedEvent:
    id: int
    post_id: strawberry.Private[int]
