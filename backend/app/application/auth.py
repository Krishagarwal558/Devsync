"""Authentication use cases."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from backend.app.application.repositories import DeviceRepository, UserRepository
from backend.app.domain.identity import Device, DeviceTrustStatus, User
from backend.app.security.passwords import PasswordHasher
from backend.app.security.tokens import TokenPair, TokenService
from shared.devsync_shared.errors import AuthenticationError, ConflictError, NotFoundError


@dataclass(frozen=True)
class RegisterUserCommand:
    """Input data for user registration."""

    email: str
    display_name: str
    password: str


class RegisterUserUseCase:
    """Registers new DevSync users."""

    def __init__(self, users: UserRepository, password_hasher: PasswordHasher) -> None:
        """Create the use case."""
        self._users = users
        self._password_hasher = password_hasher

    def execute(self, command: RegisterUserCommand) -> User:
        """Register a user and return the created domain entity."""
        normalized_email = command.email.lower().strip()
        if self._users.get_by_email(normalized_email):
            raise ConflictError("Email is already registered")
        user = User.create(
            email=normalized_email,
            display_name=command.display_name,
            password_hash=self._password_hasher.hash(command.password),
        )
        self._users.add(user)
        return user


@dataclass(frozen=True)
class LoginCommand:
    """Input data for login."""

    email: str
    password: str
    device_id: UUID | None = None


class LoginUseCase:
    """Authenticates users and issues tokens."""

    def __init__(
        self,
        users: UserRepository,
        devices: DeviceRepository,
        password_hasher: PasswordHasher,
        token_service: TokenService,
    ) -> None:
        """Create the use case."""
        self._users = users
        self._devices = devices
        self._password_hasher = password_hasher
        self._token_service = token_service

    def execute(self, command: LoginCommand) -> TokenPair:
        """Authenticate credentials and return tokens."""
        user = self._users.get_by_email(command.email)
        if user is None or not self._password_hasher.verify(command.password, user.password_hash):
            raise AuthenticationError("Invalid credentials")
        if command.device_id:
            device = self._devices.get(command.device_id)
            if device is None or device.user_id != user.id:
                raise AuthenticationError("Device is not registered to this user")
            if device.trust_status == DeviceTrustStatus.REVOKED:
                raise AuthenticationError("Device has been revoked")
        return self._token_service.issue_pair(user.id, command.device_id)


@dataclass(frozen=True)
class RegisterDeviceCommand:
    """Input data for device registration."""

    user_id: UUID
    name: str
    public_key: str


class RegisterDeviceUseCase:
    """Registers a device for later trust verification."""

    def __init__(self, users: UserRepository, devices: DeviceRepository) -> None:
        """Create the use case."""
        self._users = users
        self._devices = devices

    def execute(self, command: RegisterDeviceCommand) -> Device:
        """Register a pending device."""
        if self._users.get(command.user_id) is None:
            raise NotFoundError("User not found")
        device = Device.register(command.user_id, command.name, command.public_key)
        self._devices.add(device)
        return device


class TrustDeviceUseCase:
    """Marks a pending device as trusted."""

    def __init__(self, devices: DeviceRepository) -> None:
        """Create the use case."""
        self._devices = devices

    def execute(self, device_id: UUID) -> Device:
        """Trust a registered device."""
        device = self._devices.get(device_id)
        if device is None:
            raise NotFoundError("Device not found")
        trusted = device.trust()
        self._devices.save(trusted)
        return trusted

