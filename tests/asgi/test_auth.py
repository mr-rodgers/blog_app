import pytest
from pytest_mock import MockerFixture
import strawberry

from blog_app.core import Result
from blog_app.auth.types import Authentication, AuthError, User
from .conftest import GraphQLClient


@pytest.mark.parametrize("email", ["test@example.com"])
def test_send_login_code(client: GraphQLClient, email: str, mocker: MockerFixture):
    mocker.patch(
        "blog_app.adapters.auth0.Auth0Authenticator.send_login_code"
    ).return_value = Result(value=None)

    result = client.execute(
        """
        mutation sendLoginCode($email: String!) {
            sendLoginCode(emailAddress: $email) {
                ... on SendLoginCodeResponse {
                    emailAddress
                }
            }
        }
        """,
        variables={"email": email},
    )
    assert result.get("errors") is None
    assert result["data"] == {"sendLoginCode": {"emailAddress": email}}


@pytest.mark.parametrize(
    "authentication",
    [
        Authentication(
            access_token="foo",
            refresh_token="bar",
            user=User(id=strawberry.ID("id-1"), name="Foo Name"),
            expires_in=1000,
        )
    ],
)
@pytest.mark.parametrize("code", ["e78bc7a"])
@pytest.mark.parametrize("email", ["test@example.com"])
def test_login_with_code(
    client: GraphQLClient,
    email: str,
    code: str,
    authentication: Authentication,
    mocker: MockerFixture,
):
    """
    Check that loginWithCode() endpoint returns Authentication from
    configured authenticator.
    """
    mocker.patch(
        "blog_app.adapters.auth0.Auth0Authenticator.login_with_code"
    ).return_value = Result(value=authentication)

    result = client.execute(
        """
        mutation loginWithCode($email: String!, $code: String!) {
            loginWithCode(emailAddress: $email, code: $code) {
                ... on Authentication {
                    accessToken
                    refreshToken
                    user {
                        id
                        name
                    }
                    tokenType
                }
            }
        }
        """,
        variables={"email": email, "code": code},
    )
    assert result.get("errors") is None
    assert result["data"] == {
        "loginWithCode": {
            "accessToken": authentication.access_token,
            "refreshToken": authentication.refresh_token,
            "user": {"id": authentication.user.id, "name": authentication.user.name},
            "tokenType": "Bearer",
        }
    }


@pytest.mark.parametrize(
    "query,patch_target",
    [
        (
            """
            mutation {
                errorOperation: sendLoginCode(emailAddress: "foo@example.com") {
                    ... on AuthError {
                        reason,
                        message
                    }
                }
            }
            """,
            "blog_app.adapters.auth0.Auth0Authenticator.send_login_code",
        ),
        (
            """
            mutation {
                errorOperation: loginWithCode(emailAddress: "foo@example.com", code: "udud76") {
                    ... on AuthError {
                        reason,
                        message
                    }
                }
            }
            """,
            "blog_app.adapters.auth0.Auth0Authenticator.login_with_code",
        ),
    ],
)
@pytest.mark.parametrize(
    "autherror",
    [
        AuthError.invalid_request("Invalid request foo bar"),
        AuthError.temporary_failure("Try again later"),
    ],
)
def test_auth_mutations_auth_errors(
    client: GraphQLClient,
    query: str,
    patch_target: str,
    autherror: AuthError,
    mocker: MockerFixture,
):
    """
    Check that sendLoginCode/loginWithCode endpoint returns AuthError from
    configured authenticator as typed response.
    """
    mocker.patch(patch_target).return_value = Result(error=autherror)

    result = client.execute(query)
    assert result.get("errors") is None
    assert result["data"] == {
        "errorOperation": {
            "reason": autherror.reason.value.upper(),
            "message": autherror.originalMessage,
        }
    }


@pytest.mark.parametrize(
    "query,patch_target",
    [
        (
            """
            mutation {
                errorOperation: sendLoginCode(emailAddress: "foo@example.com") {
                    ... on AuthError {
                        reason,
                        message
                    }
                }
            }
            """,
            "blog_app.adapters.auth0.Auth0Authenticator.send_login_code",
        ),
        (
            """
            mutation {
                errorOperation: loginWithCode(emailAddress: "foo@example.com", code: "udud76") {
                    ... on AuthError {
                        reason,
                        message
                    }
                }
            }
            """,
            "blog_app.adapters.auth0.Auth0Authenticator.login_with_code",
        ),
    ],
)
def test_auth_mutations_authenticator_failure(
    client: GraphQLClient,
    query: str,
    patch_target: str,
    mocker: MockerFixture,
):
    """
    Check that sendLoginCode/loginWithCode endpoint returns internal AuthError
    when configured authenticator crashes.
    """
    mocker.patch(patch_target).side_effect = Exception()

    result = client.execute(query)
    assert result.get("errors") is None
    assert result["data"] == {
        "errorOperation": {
            "reason": "INTERNAL_ERROR",
            "message": "An internal error has occurred",
        }
    }
