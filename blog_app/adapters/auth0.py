import asyncio

from functools import partial
from typing import Any, List, Optional


import jwt
from auth0.v3.authentication import GetToken, Passwordless
from auth0.v3.management import Auth0
from auth0.v3.authentication.token_verifier import (
    TokenVerifier,
    AsymmetricSignatureVerifier,
)
from auth0.v3.exceptions import Auth0Error, RateLimitError, TokenValidationError
import strawberry
from typed_settings import settings, secret

from blog_app.auth.protocols import Authenticator
from blog_app.auth.types import (
    AuthError,
    AuthErrorReason,
    Authentication,
    LoginCodeTransport,
    User,
)
from blog_app.core.helpers import Loader
from blog_app.core.types import Result, GraphQLResult


@settings
class Auth0AuthenticatorSettings:
    domain: str = ""
    client_id: str = ""
    client_secret: str = secret(default="")
    management_api_token: str = ""


class Auth0Authenticator(Authenticator):
    AUTH_SCOPE = "openid profile email offline_access"

    def __init__(self, settings: Auth0AuthenticatorSettings):
        self.settings = settings
        self.signature_verifier = AsymmetricSignatureVerifier(
            f"https://{settings.domain}/.well-known/jwks.json"
        )
        self.management_token_fetcher = ManagementAPITokenFetcher(settings)

    def _convert_auth0_error(self, err: Auth0Error) -> AuthError:
        reason = AuthErrorReason.INVALID_REQUEST
        message: str = err.message

        if isinstance(err, RateLimitError):
            reason = AuthErrorReason.TEMPORARY_FAILURE

        elif err.error_code in [
            "bad.client_id",
            "bad.connection",
            "bad.tenant",
            "bad.authParams",
        ]:
            reason = AuthErrorReason.INTERNAL_ERROR

        return AuthError(reason=reason, message=message)

    async def _handle_token_response(
        self, data: Any
    ) -> GraphQLResult[Authentication, AuthError]:
        try:
            auth = Authentication(
                access_token=data["id_token"],
                refresh_token=data["refresh_token"],
                expires_in=data["expires_in"],
                user=await self.parse_id_token(data["id_token"]),
            )
            return GraphQLResult(value=auth)
        except TokenValidationError:
            return GraphQLResult(
                error=AuthError.invalid_token("Token validation failed.")
            )

    async def send_login_code(
        self, destination: str, destination_type: LoginCodeTransport
    ) -> GraphQLResult[None, AuthError]:
        """Send a login code using Auth0's passwordless login."""
        controller = Passwordless(self.settings.domain)
        work = (
            partial(
                controller.sms,
                self.settings.client_id,
                destination,
                self.settings.client_secret,
            )
            if destination_type == LoginCodeTransport.SMS
            else partial(
                controller.email,
                self.settings.client_id,
                destination,
                send="code",
                client_secret=self.settings.client_secret,
                auth_params={"scope": self.AUTH_SCOPE},
            )
        )

        # this runs Result.wrap(Auth0Error, work) asyncronously
        # (i.e. this thread won't block while the underlying IO is running)
        # See doc tests in blog_app/core/result:Result.wrap
        result: Result[None, Auth0Error] = await asyncio.to_thread(
            Result.wrap, Auth0Error, work
        )
        return result.map_err(self._convert_auth0_error)

    async def login_with_code(
        self, code: str, source: str, destination_type: LoginCodeTransport
    ):
        controller = GetToken(self.settings.domain)
        request_data = {
            "grant_type": "http://auth0.com/oauth/grant-type/passwordless/otp",
            "client_id": self.settings.client_id,
            "client_secret": self.settings.client_secret,
            "username": source,
            "realm": "sms" if destination_type == LoginCodeTransport.SMS else "email",
            "otp": code,
            "scope": self.AUTH_SCOPE,
        }
        result: Result[Any, Auth0Error] = await asyncio.to_thread(
            Result.wrap,
            Auth0Error,
            controller.post,
            f"https://{self.settings.domain}/oauth/token",
            data=request_data,
        )

        return await result.map_err(self._convert_auth0_error).and_then(
            self._handle_token_response
        )

    async def refresh_access_token(
        self, refresh_token: str
    ) -> GraphQLResult[Authentication, AuthError]:
        controller = GetToken(self.settings.domain)
        request_data = {
            "grant_type": "refresh_token",
            "client_id": self.settings.client_id,
            "client_secret": self.settings.client_secret,
            "refresh_token": refresh_token,
        }
        result: Result[Any, Auth0Error] = await asyncio.to_thread(
            Result.wrap,
            Auth0Error,
            controller.post,
            f"https://{self.settings.domain}/oauth/token",
            data=request_data,
        )

        return await result.map_err(self._convert_auth0_error).and_then(
            self._handle_token_response
        )

    async def parse_id_token(self, token: str) -> User:
        """Verify that the id token generated is correct and return the payload."""
        issuer = f"https://{self.settings.domain}/".format(self.settings.domain)
        tv = TokenVerifier(
            signature_verifier=self.signature_verifier,
            issuer=issuer,
            audience=self.settings.client_id,
        )
        await asyncio.to_thread(tv.verify, token)
        payload = jwt.decode(token, verify=False)

        return User(id=strawberry.ID(str(payload["sub"])), name=payload["name"])

    async def get_verified_user(self, token: str) -> GraphQLResult[User, AuthError]:
        """Get a verified user from the access token."""
        try:
            return Result(value=await self.parse_id_token(token))
        except:
            return Result(error=AuthError.invalid_token("The access token is invalid."))

    async def get_users_by_ids(self, ids: List[str]) -> List[Optional[User]]:
        """Return a list of users from auth0 api."""
        auth0 = Auth0(
            self.settings.domain, await self.management_token_fetcher.get_token()
        )
        id_repr = lambda user_id: f'"{user_id}"'
        q = "user_id:{}".format(" OR ".join(id_repr(user_id) for user_id in ids))
        users_structs = await asyncio.to_thread(auth0.users.list, q=q)

        return [
            User(id=struct["user_id"], name=struct["name"]) if struct else None
            for struct in Loader.fillBy(
                ids, users_structs["users"], lambda s: s["user_id"]
            )
        ]


class ManagementAPITokenFetcher:
    def __init__(self, settings: Auth0AuthenticatorSettings):
        self.settings = settings

    async def get_token(self) -> str:
        return self.settings.management_api_token
