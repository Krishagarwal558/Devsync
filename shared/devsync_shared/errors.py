"""Shared exception types for DevSync."""


class DevSyncError(Exception):
    """Base exception for expected DevSync failures."""


class AuthenticationError(DevSyncError):
    """Raised when credentials or tokens are invalid."""


class AuthorizationError(DevSyncError):
    """Raised when a user or device is not allowed to perform an action."""


class ConflictError(DevSyncError):
    """Raised when a state mutation conflicts with existing data."""


class NotFoundError(DevSyncError):
    """Raised when a requested entity does not exist."""

