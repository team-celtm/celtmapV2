from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus


@dataclass(slots=True)
class AppError(Exception):
    message: str
    status_code: int = HTTPStatus.BAD_REQUEST
    error_code: str = "app_error"

    def __str__(self) -> str:
        return self.message


class NotFoundError(AppError):
    def __init__(self, message: str, error_code: str = "not_found") -> None:
        super().__init__(message=message, status_code=HTTPStatus.NOT_FOUND, error_code=error_code)


class ConflictError(AppError):
    def __init__(self, message: str, error_code: str = "conflict") -> None:
        super().__init__(message=message, status_code=HTTPStatus.CONFLICT, error_code=error_code)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Unauthorized", error_code: str = "unauthorized") -> None:
        super().__init__(
            message=message, status_code=HTTPStatus.UNAUTHORIZED, error_code=error_code
        )


class IntegrationError(AppError):
    def __init__(self, message: str, error_code: str = "integration_error") -> None:
        super().__init__(
            message=message,
            status_code=HTTPStatus.BAD_GATEWAY,
            error_code=error_code,
        )
