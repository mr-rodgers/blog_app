import asyncio
import base64
import pickle
import random
import warnings
from collections.abc import Iterator
from contextlib import contextmanager
from os import environ
from typing import Any, Generic, List, Optional, Type, TypeVar, TypedDict, cast

import factory
import factory.random
import pytest
import strawberry
from pytest_factoryboy import LazyFixture, register
from pytest_mock import MockerFixture
from strawberry.asgi.constants import (
    GQL_COMPLETE,
    GQL_CONNECTION_ACK,
    GQL_CONNECTION_INIT,
    GQL_CONNECTION_KEEP_ALIVE,
    GQL_DATA,
    GQL_ERROR,
    GQL_START,
    GQL_STOP,
)

from blog_app import app, BlogApp
from blog_app.core import Result
from blog_app.core.model import ModelMap
from blog_app.auth.types import AuthError
from blog_app.database import DatabaseSettings, create_metadata, create_model_map
from blog_app.comments.types import Comment
from blog_app.posts.types import Post

from .factories import (
    CommentFactory,
    FakeComment,
    FakeUser,
    FakePost,
    PostFactory,
    UserFactory,
)
from ._testclient import TestClient


T = TypeVar("T", Post, Comment)


class Fetcher(Generic[T]):
    """Protocol for an object that allows fetching a model instance by id, directly from the DB."""

    def fetch(self, id: int) -> Optional[T]:
        ...


class GraphQLResponse(TypedDict):
    data: Any
    errors: Optional[List[Any]]


class GQLSubscription(Iterator):
    @classmethod
    @contextmanager
    def _start(cls, *, client, query, variables):
        payload = {"query": query, "variables": {} if variables is None else variables}
        op_id = str(hash(pickle.dumps(payload)))

        with client.websocket_connect("/", "graphql-ws") as ws:
            ws.send_json({"type": GQL_CONNECTION_INIT})
            assert ws.receive_json()["type"] == GQL_CONNECTION_ACK

            ws.send_json({"type": GQL_START, "id": op_id, "payload": payload})
            yield cls(ws, op_id)

    def __init__(self, ws, id):
        self._ws = ws
        self._id = id

    def __next__(self):
        data = self._ws.receive_json()

        while data["type"] == GQL_CONNECTION_KEEP_ALIVE:
            data = self._ws.receive_json()

        assert data["id"] == self._id

        if data["type"] == GQL_ERROR:
            raise ValueError(f"GQL Validation Error {repr(data['payload'])}")

        elif data["type"] == GQL_COMPLETE:
            raise StopAsyncIteration

        else:
            assert data["type"] == GQL_DATA
            return data["payload"]

    def unsubscribe(self):
        self._ws.send_json({"type": GQL_STOP, "id": self._id})


class GraphQLClient(TestClient):
    def execute(
        self, query: str, *, variables: Optional[dict] = None, access_token: str = None
    ) -> GraphQLResponse:
        headers = {}
        data = {"query": query, "variables": {} if variables is None else variables}

        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        response = self.post("/graphql", json=data, headers=headers)
        return response.json()

    def subscribe(self, query: str, *, variables: Optional[dict] = None):
        return GQLSubscription._start(client=self, query=query, variables=variables)


@pytest.fixture
def blog_app(model_map):
    app = BlogApp(debug=False, graphiql=False)
    app.model_map = model_map
    yield app


@pytest.fixture
def client(blog_app: BlogApp):
    with GraphQLClient(blog_app) as client:
        yield client


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def database_settings():
    return DatabaseSettings(  # type: ignore[call-arg]
        connection_url=environ.get(
            "TEST_DATABASE_URL",
            "mysql+aiomysql://blog_app:5678@127.0.0.1:3306/blog_app_test",
        ),
        echo_statements=False,
    )


@pytest.fixture(scope="session")
async def db_metadata(database_settings):
    # one engine per testing session is enough; we will
    # purge and drop records automatically with other
    # fixtures.
    return create_metadata(database_settings)


@pytest.fixture(scope="session")
async def model_map(db_metadata):
    metadata, model_map = db_metadata
    engine: Any = metadata.bind

    async with engine.connect() as conn:
        await conn.run_sync(metadata.drop_all)

    async with engine.connect() as conn:
        await conn.run_sync(metadata.create_all)

    yield model_map


@pytest.fixture(scope="session")
def _state():
    state = environ.get("TEST_STATE")
    random_state, locale = (None, None)
    if state:
        try:
            random_state, locale = pickle.loads(base64.b64decode(state.encode("ascii")))
        except:
            warnings.warn(
                f"Supplied testing state is invalid. Regenerating a new test state."
            )

    if not (random_state and locale):
        random_state = factory.random.get_random_state()
        locale = random.choice(["de_AT", "en_US"])
        state = base64.b64encode(pickle.dumps((random_state, locale))).decode("ascii")

    else:
        factory.random.set_random_state(random_state)

    yield (state, locale)


@pytest.fixture
def locale(_state):
    _, locale = _state
    print(f"Locale: {locale}")
    yield locale


@pytest.fixture(autouse=True)
def state(_state):
    state, _ = _state
    yield
    print("To reproduce this exact test run, set your environment:\n")
    print(f"TEST_STATE={state}")


@pytest.fixture(autouse=True)
def faker_settings(locale):
    with factory.Faker.override_default_locale(locale):
        yield


@pytest.fixture(scope="session")
def reset_fake_user_registry():
    FakeUser.registry = []


@pytest.fixture(autouse=True)
def allow_fake_user_login(mocker: MockerFixture):
    async def get_verified_user_stub(token: str):
        matching_user = next(
            (user for user in FakeUser.registry if user.access_token == token), None
        )
        return (
            Result(value=matching_user)
            if matching_user
            else Result(error=AuthError.invalid_token("invalid access token"))
        )

    async def get_users_by_ids_stub(ids: List[strawberry.ID]):
        users_by_id = {}

        for user in FakeUser.registry:
            users_by_id[user.id] = user

        return [users_by_id.get(user_id) for user_id in ids]

    get_users_by_ids_mock = mocker.patch(
        "blog_app.adapters.auth0.Auth0Authenticator.get_users_by_ids",
        wraps=get_users_by_ids_stub,
    )
    get_verified_user_mock = mocker.patch(
        "blog_app.adapters.auth0.Auth0Authenticator.get_verified_user",
        wraps=get_verified_user_stub,
    )


@pytest.fixture(autouse=True, scope="session")
def setup_auto_insert_model_factory_instances(
    model_map: ModelMap,
    event_loop: asyncio.AbstractEventLoop,
):

    post_model = model_map["post"]
    PostFactory.engine = post_model.engine
    PostFactory.table = post_model.table
    PostFactory.event_loop = event_loop

    comment_model = model_map["comment"]
    CommentFactory.engine = comment_model.engine
    CommentFactory.table = comment_model.table
    CommentFactory.event_loop = event_loop


register(UserFactory)
register(PostFactory)
register(CommentFactory)
register(UserFactory, "user")
register(PostFactory, "post")
register(CommentFactory, "comment")


@pytest.fixture
def post_fetcher(post_factory):
    return post_factory


@pytest.fixture
def comment_fetcher(comment_factory):
    return comment_factory
