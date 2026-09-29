import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field

from app.application.authenticate_user import AuthenticateUser
from app.application.change_password import ChangePassword
from app.application.logout_user import LogoutUser
from app.application.password_recovery import (
    PasswordResetEmailSender,
    RequestPasswordReset,
    ResetPassword,
)
from app.application.rotate_refresh_token import RotateRefreshToken
from app.domain.authentication import UserAccount, UserRole
from app.domain.errors import UnauthorizedException
from app.domain.password_recovery import PasswordResetEmail
from app.presentation.dependencies import (
    get_authenticate_user,
    get_change_password,
    get_logout_user,
    get_password_reset_email_sender,
    get_request_password_reset,
    get_reset_password,
    get_rotate_refresh_token,
    require_roles,
)


logger = logging.getLogger(__name__)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=150)
    password: str = Field(min_length=1, max_length=1024)


class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: str = Field(min_length=3, max_length=150)


class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=1024)


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=1, max_length=1024)


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str = Field(min_length=1, max_length=512)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class CurrentAccountResponse(BaseModel):
    id: str
    email: str
    role: UserRole
    active: bool
    district_id: str | None
    church_id: str | None


router = APIRouter(tags=["auth"])


async def _send_password_reset_email(
    sender: PasswordResetEmailSender,
    recovery_email: PasswordResetEmail,
) -> None:
    try:
        await sender.send_password_reset(recovery_email)
    except Exception as error:
        logger.warning(
            "Password reset email delivery failed",
            extra={"error_type": type(error).__name__},
        )


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


@router.get("/auth/me", response_model=CurrentAccountResponse)
async def current_account(
    actor: UserAccount = Depends(
        require_roles(UserRole.ADMIN, UserRole.PASTOR, UserRole.LIDER)
    ),
) -> CurrentAccountResponse:
    return CurrentAccountResponse(
        id=str(actor.id),
        email=actor.email,
        role=actor.role,
        active=actor.active,
        district_id=str(actor.district_id) if actor.district_id else None,
        church_id=str(actor.church_id) if actor.church_id else None,
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


@router.post("/auth/password/forgot", status_code=202, response_class=Response)
async def forgot_password(
    request: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    recovery: RequestPasswordReset = Depends(get_request_password_reset),
    sender: PasswordResetEmailSender = Depends(get_password_reset_email_sender),
) -> Response:
    recovery_email = await recovery.execute(request.email)
    if recovery_email is not None:
        background_tasks.add_task(_send_password_reset_email, sender, recovery_email)
    return Response(status_code=202)


@router.post("/auth/password/reset", status_code=204, response_class=Response)
async def reset_password(
    request: ResetPasswordRequest,
    reset: ResetPassword = Depends(get_reset_password),
) -> Response:
    try:
        await reset.execute(request.token, request.new_password)
    except UnauthorizedException as error:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_token", "message": "Token inválido o expirado"},
        ) from error
    return Response(status_code=204)


@router.post("/auth/password/change", status_code=204, response_class=Response)
async def change_password(
    request: ChangePasswordRequest,
    actor: UserAccount = Depends(
        require_roles(UserRole.ADMIN, UserRole.PASTOR, UserRole.LIDER)
    ),
    change: ChangePassword = Depends(get_change_password),
) -> Response:
    try:
        await change.execute(actor, request.current_password, request.new_password)
    except UnauthorizedException as error:
        raise HTTPException(
            status_code=401,
            detail={"code": "unauthorized", "message": "Credenciales inválidas"},
        ) from error
    return Response(status_code=204)