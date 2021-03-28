from blog_app.core.protocols import Person
from datetime import datetime
from enum import Enum

import strawberry

from blog_app.core import AppError


@strawberry.enum
class LoginCodeTransport(Enum):
    EMAIL = "email"
    SMS = "sms"


@strawberry.enum
class AuthErrorReason(Enum):
    TEMPORARY_FAILURE = "temporary_failure"
    INVALID_REQUEST = "invalid_request"
    INTERNAL_ERROR = "internal_error"
    INVALID_TOKEN = "token_validation_failed"
    UNAUTHORIZED = "unauthorized"


@strawberry.type
class AuthError(AppError):
    reason: AuthErrorReason
    originalMessage: strawberry.Private[str]

    def __init__(self, reason: AuthErrorReason, message: str):
        self.reason = reason
        self.originalMessage = message

    @strawberry.field
    def message(self) -> str:
        # when this is an internal error, hide the error
        # message.
        return (
            "An internal error has occurred"
            if self.reason == AuthErrorReason.INTERNAL_ERROR
            else self.originalMessage
        )

    @staticmethod
    def temporary_failure(message: str) -> "AuthError":
        return AuthError(reason=AuthErrorReason.TEMPORARY_FAILURE, message=message)

    @staticmethod
    def invalid_request(message: str) -> "AuthError":
        return AuthError(reason=AuthErrorReason.INVALID_REQUEST, message=message)

    @staticmethod
    def internal_error(message: str = "Internal error.") -> "AuthError":
        return AuthError(reason=AuthErrorReason.INTERNAL_ERROR, message=message)

    @staticmethod
    def invalid_token(message: str) -> "AuthError":
        return AuthError(reason=AuthErrorReason.INVALID_TOKEN, message=message)

    @staticmethod
    def unauthorized(message: str) -> "AuthError":
        return AuthError(reason=AuthErrorReason.UNAUTHORIZED, message=message)


@strawberry.type
class User(Person):
    id: strawberry.ID
    name: str


@strawberry.type
class Authentication:
    user: User
    access_token: str
    refresh_token: str
    expires_in: int

    @strawberry.field
    def token_type(self) -> str:
        return "Bearer"


@strawberry.type
class SendLoginCodeResponse:
    email_address: str


__all__ = ["AuthError", "AuthErrorReason", "LoginCodeTransport", "User"]
