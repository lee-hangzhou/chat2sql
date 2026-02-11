from typing import Optional

from app.core.singleton import Singleton
from app.services.auth import AuthService
from app.services.user import UserService


class ServiceRegistry(Singleton):
    def __init__(self) -> None:
        self._user_service: Optional[UserService] = None
        self._auth_service: Optional[AuthService] = None

    @property
    def user_service(self) -> UserService:
        if self._user_service is None:
            self._user_service = UserService()
        return self._user_service

    @property
    def auth_service(self) -> AuthService:
        if self._auth_service is None:
            self._auth_service = AuthService()
        return self._auth_service


registry = ServiceRegistry()

__all__ = ["AuthService", "UserService", "ServiceRegistry", "registry"]

