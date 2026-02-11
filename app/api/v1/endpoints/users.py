from fastapi import APIRouter, Request

from app.schemas.base import Response
from app.schemas.user import UserCreate, UserInfo
from app.services import registry

router = APIRouter()


@router.post("")
async def create_user(request: UserCreate) -> Response[UserInfo]:
    result = await registry.user_service.create_user(request)
    return Response(data=result)


@router.get("/me")
async def get_current_user(request: Request) -> Response[UserInfo]:
    user_id: int = request.state.user_id
    result = await registry.user_service.get_user_by_id(user_id)
    return Response(data=result)
