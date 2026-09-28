from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from app.application.authenticate_user import AuthenticateUser
from app.application.logout_user import LogoutUser
from app.application.rotate_refresh_token import RotateRefreshToken
from app.domain.errors import UnauthorizedException
from app.presentation.dependencies import (
    get_authenticate_user,
    get_logout_user,
    get_rotate_refresh_token,
)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=150)
    password: str = Field(min_length=1, max_length=1024)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=512)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=TokenResponse)
async def login(
    credentials: LoginRequest,
    authenticate_user: AuthenticateUser = Depends(get_authenticate_user),
) -> TokenResponse:
    try:
        tokens = await authenticate_user.execute(credentials.email, credentials.password)
    except UnauthorizedException as error:
        raise HTTPException(
            status_code=401,
            detail={"code": "unauthorized", "message": "Credenciales inválidas"},
        ) from error

    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.access_expires_in,
    )


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh(
    request: RefreshRequest,
    rotate_refresh_token: RotateRefreshToken = Depends(get_rotate_refresh_token),
) -> TokenResponse:
    try:
        tokens = await rotate_refresh_token.execute(request.refresh_token)
    except UnauthorizedException as error:
        raise HTTPException(
            status_code=401,
            detail={"code": "unauthorized", "message": "Credenciales inválidas"},
        ) from error

    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.access_expires_in,
    )


@router.post("/auth/logout", status_code=204, response_class=Response)
async def logout(
    request: RefreshRequest,
    logout_user: LogoutUser = Depends(get_logout_user),
) -> Response:
    await logout_user.execute(request.refresh_token)
    return Response(status_code=204)