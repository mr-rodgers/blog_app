from typing import Any
from dataclasses import dataclass

import pytest
import strawberry
from strawberry.types import Info
from strawberry.dataloader import DataLoader

from blog_app.auth.types import (
    AuthError,
    AuthErrorReason,
    Authentication,
    SendLoginCodeResponse,
    User,
)
from blog_app.auth.context import Context
from blog_app.auth.resolvers import send_login_code, login_with_code
from blog_app.core import AppRequest, AppContext, Result
from blog_app.core.protocols import AuthContext, CommentContext, PostContext
from .conftest import MockAuthenticator


@dataclass
class MockAppContext:
    auth: AuthContext
    posts: PostContext
    comments: CommentContext
    request: AppRequest


@dataclass
class MockInfo:
    context: AppContext


@pytest.fixture
def info(authenticator, mocker):
    return MockInfo(
        context=MockAppContext(
            auth=Context(
                authenticator=authenticator,
                request=mocker.Mock(AppRequest),
                users=mocker.Mock(DataLoader),
            ),
            posts=mocker.Mock(PostContext),
            comments=mocker.Mock(CommentContext),
            request=mocker.Mock(AppRequest),
        )
    )


@pytest.mark.parametrize("email", ["test@example.com"])
@pytest.mark.asyncio
async def test_send_login_code_calls_authenticator(
    email: str, info: Info, authenticator: MockAuthenticator
):
    """Check that send_login_code resolver uses authenticator."""
    authenticator.send_login_code.return_value = Result(value=None)

    result = await send_login_code(email, info)
    assert isinstance(result, SendLoginCodeResponse)


@pytest.mark.parametrize(
    "error",
    [
        AuthError.internal_error("Something happened"),
        AuthError.temporary_failure("Something happened"),
        AuthError.invalid_request("Something happened"),
    ],
)
@pytest.mark.parametrize("email", ["test@example.com"])
@pytest.mark.asyncio
async def test_send_login_code_returns_auth_error_on_authenticator_auth_error(
    email: str, info: Info, authenticator: MockAuthenticator, error: AuthError
):
    """Check that send_login_code returns auth error from authenticator."""
    authenticator.send_login_code.return_value = Result(error=error)

    result = await send_login_code(email, info)
    assert result == error


@pytest.mark.parametrize("email", ["test@example.com"])
@pytest.mark.asyncio
async def test_send_login_code_returns_auth_error_on_authenticator_exception(
    email: str, info: Info, authenticator: MockAuthenticator
):
    """Check that send_login_code returns AuthError if authenticator throws an exception."""
    authenticator.send_login_code.side_effect = Exception()

    result = await send_login_code(email, info)
    assert isinstance(result, AuthError)
    assert result.reason == AuthErrorReason.INTERNAL_ERROR


@pytest.mark.parametrize(
    "result",
    [
        Result(error=AuthError.internal_error("Something happened")),
        Result(error=AuthError.temporary_failure("Something happened")),
        Result(error=AuthError.invalid_request("Something happened")),
        Result(error=AuthError.invalid_token("Something happened")),
        Result(
            value=Authentication(
                user=User(id=strawberry.ID("foo"), name="Someone's Name"),
                access_token="foo",
                refresh_token="bar",
                expires_in=0,
            )
        ),
    ],
)
@pytest.mark.asyncio
async def test_login_with_code_calls_authenticator(
    info: Info, authenticator: MockAuthenticator, result: Result
):
    """Check that send_login_code resolver uses authenticator and passes the result through."""
    authenticator.login_with_code.return_value = result

    assert (
        await login_with_code("InR5cCI6", "test@example.com", info)
    ) == result.collapse()


@pytest.mark.asyncio
async def test_login_with_code_returns_internal_auth_error_on_authenticator_exception(
    info: Info, authenticator: MockAuthenticator
):
    """Check that send_login_code resolver uses authenticator and passes the result through."""
    authenticator.login_with_code.side_effect = Exception()

    result = await login_with_code("InR5cCI6", "test@example.com", info)
    assert isinstance(result, AuthError)
    assert result.reason == AuthErrorReason.INTERNAL_ERROR
