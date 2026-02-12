from typing import Optional

from app.core.singleton import Singleton
from app.services.auth import AuthService
from app.services.chat import ChatService
from app.services.schema import SchemaService
from app.services.user import UserService


class ServiceRegistry(Singleton):
    def __init__(self) -> None:
        self._user_service: Optional[UserService] = None
        self._auth_service: Optional[AuthService] = None
        self._chat_service: Optional[ChatService] = None
        self._schema_service: Optional[SchemaService] = None

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

    @property
    def chat_service(self) -> ChatService:
        if self._chat_service is None:
            self._chat_service = ChatService()
        return self._chat_service

    @property
    def schema_service(self) -> SchemaService:
        if self._schema_service is None:
            self._schema_service = SchemaService()
        return self._schema_service


registry = ServiceRegistry()
