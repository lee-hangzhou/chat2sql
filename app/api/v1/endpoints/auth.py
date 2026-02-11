from fastapi import APIRouter, Request

from app.schemas.auth import LoginRequest, LoginResponse, RefreshRequest, TokenResponse
from app.schemas.base import Response
from app.schemas.user import UserCreate, UserInfo
from app.services import registry

router = APIRouter()


@router.post("/register")
async def register(request: UserCreate) -> Response[UserInfo]:
    result = await registry.user_service.create_user(request)
    return Response(data=result)


@router.post("/login")
async def login(request: LoginRequest) -> Response[LoginResponse]:
    result = await registry.auth_service.login(request.username, request.password)
    return Response(data=result)


@router.post("/refresh")
async def refresh_token(request: RefreshRequest) -> Response[TokenResponse]:
    result = await registry.auth_service.refresh_token(request.refresh_token)
    return Response(data=result)


@router.post("/logout")
async def logout(request: Request) -> Response[None]:
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.removeprefix("Bearer ").strip()
    await registry.auth_service.logout(token)
    return Response(data=None, msg="Logged out")
