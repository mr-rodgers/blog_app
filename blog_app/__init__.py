import logging
import traceback
from typing import Any, AsyncGenerator, List, Optional, Union
from starlette.types import Receive, Scope, Send

import strawberry
from strawberry.asgi import GraphQL, ExecutionResult, GraphQLHTTPResponse

from .core import AppRequest
from .adapters.auth0 import Auth0Authenticator
from .auth.resolvers import send_login_code, login_with_code, refresh_login
from .comments.resolvers import add_comment, update_comment, delete_comment
from .comments.types import Comment
from .events import (
    Events,
    Matcher,
    CommentAddedEvent,
    PostDeletedEvent,
    PostUpdatedEvent,
)
from .events.demo_pubsub import DemoPubsub
from .posts.resolvers import get_posts, create_post, update_post, delete_post
from .posts.types import Post
from .reactions.resolvers import set_reaction, delete_reaction
from .reactions.types import Reaction
from .context import build_context
from .database import create_model_map
from .settings import load, Settings


evts = Events()


@strawberry.type
class Query:
    posts = strawberry.field(
        get_posts, description="Retreive a queryable collection of posts."
    )


@strawberry.type
class Mutation:
    send_login_code = strawberry.field(
        send_login_code,
        description="Send a code to the provided email address, which can"
        " be used with `loginWithCode` to authenticate.",
    )
    login_with_code = strawberry.field(
        login_with_code,
        description="Authenticate using a code that was sent to the"
        " provided email address using `sendLoginCode`",
    )
    refresh_login = strawberry.field(
        refresh_login,
        description="Re-authenticate using the `refreshToken` from the last"
        " authentication.",
    )
    create_post = strawberry.field(
        create_post,
        description="Create a new post" " with supplied `title` and `content`.",
    )
    update_post = strawberry.field(
        evts.track(update_post, generating=PostUpdatedEvent),
        description="Update the post"
        " with the given `id`, setting the `title` and `content` to new values"
        " when provided.",
    )
    delete_post = strawberry.field(
        evts.track(delete_post, generating=PostDeletedEvent),
        description="Delete the post"
        " with the given `id`. All attached comments (and reactions to those comments)"
        " will also be deleted.",
    )
    add_comment = strawberry.field(
        evts.track(add_comment, generating=CommentAddedEvent),
        description="Add a comment to the post with the given `postId`.",
    )
    update_comment = strawberry.field(
        update_comment, description="Update the comment with the given `id`."
    )
    delete_comment = strawberry.field(
        delete_comment, description="Remove the comment with the given `id`."
    )

    # reaction mutations
    set_reaction = strawberry.field(
        set_reaction,
        description="Set a reaction to the comment with the given `commentId`."
        " Any previously set reactions by the logged in user to the same comment"
        " are removed.",
    )
    delete_reaction = strawberry.field(
        delete_reaction, description="Delete the reaction with the given `id`."
    )


@strawberry.type
class Subscription:
    @strawberry.subscription
    def watch_post(
        self, id: int
    ) -> AsyncGenerator[
        Union[PostUpdatedEvent, PostDeletedEvent, CommentAddedEvent], None
    ]:
        return evts.stream(
            Matcher(PostUpdatedEvent, id=id),
            Matcher(PostDeletedEvent, id=id),
            Matcher(CommentAddedEvent, post_id=id),
        )


class BlogApp(GraphQL):
    settings: Settings

    def __init__(self, **kwargs):
        # These are types that strawberry can't detect because they aren't returned
        # directly from any resolver.

        additional_types = [Post, Comment, Reaction]
        kwargs.setdefault(
            "schema",
            strawberry.Schema(
                query=Query,
                mutation=Mutation,
                subscription=Subscription,
                types=additional_types,
            ),
        )
        super().__init__(**kwargs)

        self.settings = load()
        self.model_map = create_model_map(self.settings.database)

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] == "lifespan":
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    await self.startup()
                    await send({"type": "lifespan.startup.complete"})
                elif message["type"] == "lifespan.shutdown":
                    await self.shutdown()
                    await send({"type": "lifespan.shutdown.complete"})
                    return
        else:
            await super().__call__(scope, receive, send)

    async def startup(self):
        # here is where we can set up a bonafide Pubsub
        # adapter.
        evts.pubsub = DemoPubsub()

    async def shutdown(self):
        # the same db engine is shared by all modules
        await self.model_map["post"].engine.dispose()

        assert evts.pubsub is not None
        await evts.pubsub.dispose()

    async def get_context(
        self, request: AppRequest, response: Optional[Any] = None
    ) -> Optional[Any]:
        authenticator = Auth0Authenticator(self.settings.auth)
        return await build_context(
            request=request,
            authenticator=authenticator,
            model_map=self.model_map,
        )

    async def process_result(
        self, request: AppRequest, result: ExecutionResult
    ) -> GraphQLHTTPResponse:
        data: GraphQLHTTPResponse = {"data": result.data}

        if result.errors:
            data["errors"] = [err.formatted for err in result.errors]

            for error in result.errors:
                logging.error("An unhandled application error has occurred.")
                if error.original_error:
                    logging.error(
                        "".join(traceback.format_tb(error.original_error.__traceback__))
                    )

        return data


app = BlogApp(graphiql=False)
_debug_app = BlogApp(debug=True, graphiql=True)
