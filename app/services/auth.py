from app.core.config import settings
from app.core.redis import redis_client
from app.core.security import (
    active_token_key,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.exceptions.base import InvalidCredentialsError, InvalidTokenError
from app.repositories.user import UserRepository
from app.schemas.auth import LoginResponse, TokenResponse

# access_token 的 Redis TTL（秒）
_ACCESS_TOKEN_TTL = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60


class AuthService:
    def __init__(self) -> None:
        self.user_repo = UserRepository()

    async def login(self, username: str, password: str) -> LoginResponse:
        user = await self.user_repo.get_by_username(username)
        if not user or not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError()

        access_token = create_access_token(subject=user.id)
        refresh_token = create_refresh_token(subject=user.id)

        await redis_client.set(
            active_token_key(access_token), str(user.id), ex=_ACCESS_TOKEN_TTL
        )

        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
        )

    @staticmethod
    async def refresh_token(refresh_token: str) -> TokenResponse:
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise InvalidTokenError()

        user_id_raw = payload.get("sub")
        if not user_id_raw:
            raise InvalidTokenError()

        if isinstance(user_id_raw, (str, int)):
            user_id = user_id_raw
        else:
            raise InvalidTokenError()

        access_token = create_access_token(subject=user_id)

        await redis_client.set(
            active_token_key(access_token), str(user_id), ex=_ACCESS_TOKEN_TTL
        )

        return TokenResponse(access_token=access_token)

    @staticmethod
    async def logout(token: str) -> None:
        """从 Redis 中删除 token，使其立即失效"""
        await redis_client.delete(active_token_key(token))
