from fastapi import APIRouter, Request

from app.schemas.auth import LoginRequest, LoginResponse, RefreshRequest, TokenResponse
from app.schemas.base import Response
from app.services import registry

router = APIRouter()


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
    _ = request.state.user_id
    return Response(data=None, msg="Logged out")
