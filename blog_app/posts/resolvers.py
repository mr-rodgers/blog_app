import logging
from typing import Optional, Union, cast

from strawberry.types import Info

from blog_app.core import (
    AppContext,
    AppRequest,
    AppError,
    AppPost,
    InternalError,
    ItemNotFoundError,
)
from blog_app.core.helpers import QueryableCollection
from blog_app.auth.types import AuthError
from blog_app.common.logic import (
    EditType,
    handle_create,
    handle_edit,
    Unauthorized,
    remove_falsy_values,
)
from .context import Context
from .types import (
    PostCreationResponse,
    PostDeletionResponse,
    PostTitle,
    PostUpdateResponse,
)

PostError = Union[AuthError, InternalError]
PostEditError = Union[PostError, ItemNotFoundError]


def coerce_error(err: AppError) -> PostError:
    if isinstance(err, (AuthError, InternalError)):
        return err
    else:
        logging.error("Unexpect app error: '%s'", err.message)
        return InternalError()


def coerce_edit_error(err: AppError) -> PostEditError:
    if isinstance(err, Unauthorized):
        return AuthError.unauthorized("No authority to edit this post.")
    if isinstance(err, ItemNotFoundError):
        return ItemNotFoundError("No such post.")
    else:
        return coerce_error(err)


def get_loader(info: Info[AppContext, AppRequest]):
    # The implementation of the PostContext protocol is provided by the
    # posts (this) package, and is guaranteed to be a Context.
    return cast(Context, info.context.posts).loader


def get_posts_model(info: Info[AppContext, AppRequest]):
    return cast(Context, info.context.posts).model


async def get_posts(info: Info[AppContext, AppRequest]) -> QueryableCollection[AppPost]:
    return QueryableCollection(loader=get_loader(info))


async def create_post(
    title: PostTitle, content: str, info: Info[AppContext, AppRequest]
) -> Union[PostCreationResponse, PostError]:
    return (
        (
            await handle_create(
                {"title": title, "content": content},
                info.context.auth,
                get_posts_model(info),
            )
        )
        .map(lambda id: PostCreationResponse(id=id, title=title))
        .map_err(coerce_error)
        .collapse()
    )


async def update_post(
    id: int,
    info: Info[AppContext, AppRequest],
    *,
    title: Optional[PostTitle] = None,
    content: Optional[str] = None,
) -> Union[PostUpdateResponse, PostEditError]:
    args = remove_falsy_values({"title": title, "content": content})
    return (
        (
            await handle_edit(
                id,
                info.context.auth,
                get_loader(info),
                EditType.UPDATE,
                **args,
            )
        )
        .map(lambda _: PostUpdateResponse(id=id, **args))
        .map_err(coerce_edit_error)
        .collapse()
    )


async def delete_post(
    id: int,
    info: Info[AppContext, AppRequest],
) -> Union[PostDeletionResponse, PostEditError]:
    return (
        (
            await handle_edit(
                id,
                info.context.auth,
                get_loader(info),
                EditType.DELETE,
            )
        )
        .map(lambda _: PostDeletionResponse(id=id))
        .map_err(coerce_edit_error)
        .collapse()
    )


__all__ = ["get_posts"]
