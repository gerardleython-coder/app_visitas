from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.application.authenticate_user import AuthenticateUser
from app.domain.errors import UnauthorizedException
from app.presentation.dependencies import get_authenticate_user


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=150)
    password: str = Field(min_length=1, max_length=1024)


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