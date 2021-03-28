from typing import Any, Callable, Dict, cast

import jwt
import pytest
from auth0.v3.exceptions import TokenValidationError
from requests import Request

from blog_app.adapters.auth0 import Auth0Authenticator, Auth0AuthenticatorSettings
from blog_app.auth.types import (
    AuthError,
    AuthErrorReason,
    Authentication,
    LoginCodeTransport,
    User,
)
from blog_app.core import Result


class APIStub:
    def __init__(self, requests_mock, settings):
        self.requests_mock = requests_mock
        self.settings = settings

    def override_responder(self, *, data=None, status_code=None):
        # wrap a responder with a function that will override
        # response data or status code, when provided.
        def decorator(func: Callable[[Request, Any], Any]):
            def wrapper(request: Request, context):
                if status_code is not None:
                    context.status_code = status_code

                return func(request, context) if data is None else data

            return wrapper

        return decorator

    def passwordless(self, *, data=None, status_code=None):
        @self.override_responder(data=data, status_code=status_code)
        def responder(request: Request, _):
            request_data = request.json()
            response_data: Dict[str, Any] = {"_id": "372837237823783"}

            if request_data["connection"] == "email":
                response_data.update(
                    {
                        "email": request_data["email"],
                        "email_verified": False,
                    }
                )

            if request_data["connection"] == "sms":
                response_data.update({"phone_number": request_data["phone_number"]})

            return response_data

        self.requests_mock.register_uri(
            "POST", f"https://{self.settings.domain}/passwordless/start", json=responder
        )

        return self.requests_mock

    def oauth(self, *, data=None, status_code=None):
        @self.override_responder(data=data, status_code=status_code)
        def responder(request: Request, _):
            response_data: Dict[str, Any] = {
                "access_token": "K8F2FlCy8puKJaOvVpVstpyueE91",
                "refresh_token": "v1.MaUU9gDvF7NKjgshqNIdD09qR93dQLaVsH7utXHqFhf-6NDU",
                "id_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6IldrQmxLam9WNUttdlZXdW94bGtLbCJ9.eyJuaWNrbmFtZSI6InRqZC5yb2RnZXJzIiwibmFtZSI6InRqZC5yb2RnZXJzQGdtYWlsLmNvbSIsInBpY3R1cmUiOiJodHRwczovL3MuZ3JhdmF0YXIuY29tL2F2YXRhci9mZjgyNTk4MDFlMjNkNjgwMTA1ZTNjODRmMGVkNDZhMz9zPTQ4MCZyPXBnJmQ9aHR0cHMlM0ElMkYlMkZjZG4uYXV0aDAuY29tJTJGYXZhdGFycyUyRnRqLnBuZyIsInVwZGF0ZWRfYXQiOiIyMDIxLTAzLTA4VDE3OjI0OjEwLjU5MFoiLCJlbWFpbCI6InRqZC5yb2RnZXJzQGdtYWlsLmNvbSIsImVtYWlsX3ZlcmlmaWVkIjp0cnVlLCJpc3MiOiJodHRwczovL2Rldi1qN3c5aGV3eS5ldS5hdXRoMC5jb20vIiwic3ViIjoiZW1haWx8NjA0NTI1MzExZmViZmRkY2NjMzRmODI1IiwiYXVkIjoiOFB4UlVhcFkzdWZ1MGxHQ3YxQ09ZSGVxa0NodlF5czkiLCJpYXQiOjE2MTUyMjQyNTAsImV4cCI6MTYxNTI2MDI1MH0.WPgxmlKzab6quv9W0Gl8xGZbDPucpn9cPt7wa7WrrWtYa62PD1SbMVM9KoWR6Fn-DLzouODC6VKQia8tbC90jkxoYduL1IJDRpQcRSoyIjbuUbjp00N7DrQYlXUc-GwCKD05iYaQE9_bcJtc5LfsmZqPdq0u-FlzeN5fSWPhUBD4RIBur4JWIPJwaLTWes-WpSovG_RJk-4mavmc0aSYR9F-Rizyl3DlXnYfeI5wxjKUF7D-HCT3WKrJ4-oqWe37Xfz0J_kDUhPKoULSNeDhOk2QqXQuY3uyOw1SRlMYcMrtQM0v6dGd53Oql-u9rZB1XPp8bw4kJRDaApN8zwh17A",
                "scope": "openid profile email offline_access",
                "expires_in": 86400,
                "token_type": "Bearer",
            }

            return response_data

        self.requests_mock.register_uri(
            "POST", f"https://{self.settings.domain}/oauth/token", json=responder
        )
        return self.requests_mock

    def users(self, *, data=None, status_code=None):
        @self.override_responder(data=data, status_code=status_code)
        def responder(request: Request, _):
            response_data: Dict[str, Any] = {
                "users": [
                    {
                        "user_id": "1",
                        "name": "Tom",
                    },
                    {
                        "user_id": "2",
                        "name": "Tim",
                    },
                ]
            }

            return response_data

        self.requests_mock.register_uri(
            "GET", f"https://{self.settings.domain}/api/v2/users", json=responder
        )
        return self.requests_mock


@pytest.fixture
def settings():
    # these aren't supposed to be instantiated directly,
    # so mypy complains.
    return Auth0AuthenticatorSettings(  # type: ignore
        domain="test.example.com",
        client_id="dummy-client-id",
        client_secret="dummy-client-secret",
    )


@pytest.fixture
def authenticator(settings):
    return Auth0Authenticator(settings)


@pytest.fixture
def api_stub(requests_mock, settings):
    # fixture that creates stub responders for the
    # passwordless api
    return APIStub(requests_mock, settings)


@pytest.mark.parametrize(
    "destination,transport",
    [
        ("test@example.com", LoginCodeTransport.EMAIL),
        ("+649837744473", LoginCodeTransport.SMS),
    ],
)
@pytest.mark.asyncio
async def test_send_login_code_uses_passwordless(
    destination: str,
    transport: LoginCodeTransport,
    api_stub: APIStub,
    settings: Auth0AuthenticatorSettings,
    authenticator: Auth0Authenticator,
):
    mock = api_stub.passwordless()
    result = await authenticator.send_login_code(destination, transport)

    assert isinstance(result, Result)
    assert result.is_ok
    assert mock.called

    last_request = mock.last_request
    assert last_request.path == "/passwordless/start"
    assert last_request.hostname == settings.domain

    expected_request_data: Dict[str, Any] = {
        "client_id": settings.client_id,
        "client_secret": settings.client_secret,
    }

    if transport == LoginCodeTransport.EMAIL:
        expected_request_data.update(
            {
                "email": destination,
                "connection": "email",
                "send": "code",
                "authParams": {
                    "scope": "openid profile email offline_access",
                },
            }
        )

    if transport == LoginCodeTransport.SMS:
        expected_request_data.update({"phone_number": destination, "connection": "sms"})

    assert last_request.json() == expected_request_data


@pytest.mark.parametrize("code", ["1NiIsInR5tpZCI6UttdlZXdW94bGtL"])
@pytest.mark.parametrize(
    "source,transport",
    [
        ("test@example.com", LoginCodeTransport.EMAIL),
        ("+649837744473", LoginCodeTransport.SMS),
    ],
)
@pytest.mark.asyncio
async def test_verify_login_code(
    code: str,
    source: str,
    transport: LoginCodeTransport,
    api_stub: APIStub,
    settings: Auth0AuthenticatorSettings,
    authenticator: Auth0Authenticator,
    mocker,
):
    mock = api_stub.oauth()
    mocker.patch("auth0.v3.authentication.token_verifier.TokenVerifier.verify")
    result = await authenticator.login_with_code(code, source, transport)

    assert isinstance(result, Result)
    assert result.is_ok
    assert mock.called

    last_request = mock.last_request
    assert last_request.path == "/oauth/token"
    assert last_request.hostname == settings.domain

    expected_request_data = {
        "client_id": settings.client_id,
        "client_secret": settings.client_secret,
        "realm": "email" if transport == LoginCodeTransport.EMAIL else "sms",
        "username": source,
        "otp": code,
        "grant_type": "http://auth0.com/oauth/grant-type/passwordless/otp",
        "scope": "openid profile email offline_access",
    }

    assert last_request.json() == expected_request_data
    assert isinstance(result.collapse(), Authentication)


@pytest.mark.parametrize("code", ["cCI6IkpXVCIsIm"])
@pytest.mark.parametrize(
    "source,transport",
    [
        ("test@example.com", LoginCodeTransport.EMAIL),
        ("+649837744473", LoginCodeTransport.SMS),
    ],
)
@pytest.mark.asyncio
async def test_verify_login_code_auth_error_on_forbidden(
    code: str,
    source: str,
    transport: LoginCodeTransport,
    api_stub: APIStub,
    authenticator: Auth0Authenticator,
):
    mock = api_stub.oauth(
        status_code=403,
        data={
            "error": "unauthorized_client",
            "error_description": "Grant type 'http://auth0.com/oauth/grant-type/passwordless/otp' not allowed for the client.",
            "error_uri": "https://auth0.com/docs/clients/client-grant-types",
        },
    )
    result = await authenticator.login_with_code(code, source, transport)
    assert isinstance(result.collapse(), AuthError)


@pytest.mark.parametrize("code", ["IldrQmxLam9WN"])
@pytest.mark.parametrize(
    "source,transport",
    [
        ("test@example.com", LoginCodeTransport.EMAIL),
        ("+649837744473", LoginCodeTransport.SMS),
    ],
)
@pytest.mark.asyncio
async def test_login_with_code_auth_error_on_invalid_id_token(
    code: str,
    source: str,
    transport: LoginCodeTransport,
    api_stub: APIStub,
    authenticator: Auth0Authenticator,
):
    mock = api_stub.oauth(
        data={
            "access_token": "K8F2FlCy8puKJaOvVpVstpyueE91",
            "refresh_token": "v1.MaUU9gDvF7NKjgshqNIdD09qR93dQLaVsH7utXHqFhf-6NDU",
            "id_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IksImtpZCI6IldrQmxLam9WNUttdlZXdW94bGtLbCJ9.eyJuaWNrbmFtZSI6InRqZC5yb2RnZXJzIiwibmFtZSI6InRqZC5yblsLmNvbSIsInBpY3R1cmUiOiJodHRwczovL3MuZ3JhdmF0YXIuY29tL2F2YXRhci9mZjgyNTk4MDFlMjNkNjgwMTA1ZTNjODRmMGVkNDZhMz9zPTQ4MCZyPXBnJmQ9aHR0cHMlM0ElMkYlMkZjZG4uYXV0aDAuY29tJTJGYXZhdGFycyUyRnRqLnBuZyIsInVwZGF0ZWRfYXQiOiIyMDIxLTAzLTA4VDE3OjI0OjEwLjU5MFoiLCJlbWFpbCI6InRqZC5yb2RnZXJzQGdtYWlsLmNvbSIsImVtYWlsX3ZlcmlmaWVkIjp0cnVlLCJpc3MiOiJodHRwczovL2Rldi1qN3c5aGV3eS5ldS5hdXRoMC5jb20vIiwic3ViIjoiZW1haWx8NjA0NTI1MzExZmViZmRkY2NjMzRmODI1IiwiYXVkIjoiOFB4UlVhcFkzdWZ1MGxHQ3YxQ09ZSGVxa0NodlF5czkiLCJpYXQiOjE2MTUyMjQyNTAsImV4cCI6MTYxNTI2MDI1MH0.WPgxmlKzab6quv9W0Gl8xGZbDPucpn9cPt7wa7WrrWtYa62PD1SbMVM9KoWR6Fn-DLzouODC6VKQia8tbC90jkxoYduL1IJDRpQcRSoyIjbuUbjp00N7DrQYlXUc-GwCKD05iYaQE9_bcJtc5LfsmZqPdq0u-FlzeN5fSWPhUBD4RIBur4JWIPJwaLTWes-WpSovG_RJk-4mavmc0aSYR9F-Rizyl3DlXnYfeI5wxjKUF7D-HCT3WKrJ4-oqWe37Xfz0J_kDUhPKoULSNeDhOk2QqXQuY3uyOw1SRlMYcMrtQM0v6dGd53Oql-u9rZB1XPp8bw4kJRDaApN8zwh17A",
            "scope": "openid profile email offline_access",
            "expires_in": 86400,
            "token_type": "Bearer",
        },
    )
    result = await authenticator.login_with_code(code, source, transport)
    assert isinstance(result.collapse(), AuthError)


@pytest.mark.parametrize(
    "token", ["v1.MaUU9gDvF7NKjgshqNIdD09qR93dQLaVsH7utXHqFhf-6NDU"]
)
@pytest.mark.asyncio
async def test_refresh_access_token(
    token: str,
    api_stub: APIStub,
    settings: Auth0AuthenticatorSettings,
    authenticator: Auth0Authenticator,
    mocker,
):
    mock = api_stub.oauth()
    mocker.patch("auth0.v3.authentication.token_verifier.TokenVerifier.verify")
    result = await authenticator.refresh_access_token(token)

    assert isinstance(result, Result)
    assert result.is_ok
    assert mock.called

    last_request = mock.last_request
    assert last_request.path == "/oauth/token"
    assert last_request.hostname == settings.domain

    expected_request_data = {
        "client_id": settings.client_id,
        "client_secret": settings.client_secret,
        "grant_type": "refresh_token",
        "refresh_token": token,
    }

    assert last_request.json() == expected_request_data
    assert isinstance(result.collapse(), Authentication)


@pytest.mark.parametrize(
    "ids,expected_users",
    [
        (["1", "2"], [User(id="1", name="Tom"), User(id="2", name="Tim")]),  # type: ignore
        (["2", "2"], [User(id="2", name="Tim"), User(id="2", name="Tim")]),  # type: ignore
        (["5", "1"], [None, User(id="1", name="Tom")]),  # type: ignore
        (["134", "23"], [None, None]),
    ],
)
@pytest.mark.asyncio
async def test_get_users_by_ids(
    ids,
    expected_users,
    api_stub: APIStub,
    settings: Auth0AuthenticatorSettings,
    authenticator: Auth0Authenticator,
    mocker,
):
    mock = api_stub.users()
    mocker.patch("auth0.v3.authentication.token_verifier.TokenVerifier.verify")
    received_users = await authenticator.get_users_by_ids(ids)

    last_request = mock.last_request
    assert last_request.path == "/api/v2/users"
    assert last_request.hostname == settings.domain
    assert "q=user_id" in last_request.query

    for received, expected in zip(received_users, expected_users):
        if received is None:
            assert expected is None

        else:
            assert received.id == expected.id
            assert received.name == expected.name


@pytest.mark.parametrize(
    "destination,transport",
    [
        ("test@example.com", LoginCodeTransport.EMAIL),
        ("+649837744473", LoginCodeTransport.SMS),
    ],
)
@pytest.mark.parametrize(
    "error_data,status_code,expected_reason",
    [
        (
            {
                "error": "bad.connection",
                "error_description": "Connection does not exist",
            },
            400,
            AuthErrorReason.INTERNAL_ERROR,
        ),
        (
            {
                "error": "bad.request",
                "error_description": "The following properties are not allowed: age",
            },
            400,
            AuthErrorReason.INVALID_REQUEST,
        ),
        (
            {
                "error": "too_many_requests",
                "error_description": "Rate limit exceeded",
            },
            429,
            AuthErrorReason.TEMPORARY_FAILURE,
        ),
    ],
)
@pytest.mark.asyncio
async def test_send_login_code_wraps_errors_in_results(
    destination: str,
    transport: LoginCodeTransport,
    error_data: Any,
    status_code: int,
    expected_reason: AuthErrorReason,
    api_stub: APIStub,
    authenticator: Auth0Authenticator,
):
    mock = api_stub.passwordless(
        status_code=status_code,
        data=error_data,
    )

    result = await authenticator.send_login_code(destination, transport)

    assert isinstance(result, Result)
    assert result.is_failed

    err = cast(AuthError, result.as_tuple()[1])
    assert err.reason == expected_reason


@pytest.mark.parametrize("user_id", [123456, "foo-id-283"])
@pytest.mark.parametrize("name", ["Foo User"])
@pytest.mark.asyncio
async def test_get_verified_user_returns_user_props_from_id_token(
    user_id, name, mocker, authenticator: Auth0Authenticator
):
    mocker.patch("auth0.v3.authentication.token_verifier.TokenVerifier.verify")
    token = jwt.encode(
        {"sub": user_id, "name": name}, "secret", algorithm="HS256"
    ).decode("utf8")

    result = (await authenticator.get_verified_user(token)).collapse()
    assert isinstance(result, User)
    assert result.id == str(user_id)
    assert result.name == name


@pytest.mark.parametrize("error", [TokenValidationError(), Exception()])
@pytest.mark.parametrize("user_id", [123456, "foo-id-283"])
@pytest.mark.parametrize("name", ["Foo User"])
@pytest.mark.asyncio
async def test_get_verified_user_returns_auth_error_on_invalid_token(
    user_id, name, error, mocker, authenticator: Auth0Authenticator
):
    """
    Check that get_verified_user() returns an auth error with INVALID_TOKEN
    reason whenever token validation fails.
    """
    mocker.patch(
        "auth0.v3.authentication.token_verifier.TokenVerifier.verify"
    ).side_effect = error
    token = jwt.encode(
        {"sub": user_id, "name": name}, "secret", algorithm="HS256"
    ).decode("utf8")

    result = (await authenticator.get_verified_user(token)).collapse()
    assert isinstance(result, AuthError)
    assert result.reason == AuthErrorReason.INVALID_TOKEN


@pytest.mark.parametrize("payload", [{"sub": "id-foo"}, {"name": "Tim Burton"}])
@pytest.mark.asyncio
async def test_get_verified_user_returns_auth_error_on_missing_field(
    payload, mocker, authenticator: Auth0Authenticator
):
    """
    Check that get_verified_user() returns an auth error with INVALID_TOKEN
    reason whenever token has incomplete payload.
    """
    mocker.patch("auth0.v3.authentication.token_verifier.TokenVerifier.verify")
    token = jwt.encode(payload, "secret", algorithm="HS256").decode("utf8")

    result = (await authenticator.get_verified_user(token)).collapse()
    assert isinstance(result, AuthError)
    assert result.reason == AuthErrorReason.INVALID_TOKEN
