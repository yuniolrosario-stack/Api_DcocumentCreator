import logging
from typing import Optional
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, status

from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import User
from app.schemas.auth import LoginInput, TokenResponse, UserResponse, RefreshTokenInput
from app.core.security import verify_password, create_access_token, decode_access_token
from app.core.auth_dependencies import get_current_user
from app.core.config import settings
from app.middleware.security import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["Autenticación"])


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Endpoint de Autenticación de Usuarios (JWT)"
)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
async def login(
    request: Request,
    credentials: LoginInput,
    db: Session = Depends(get_db)
):
    """
    ## Inicio de Sesión de Usuarios
    - Recibe `username` y `password` únicamente (**NO correo electrónico**).
    - Valida credenciales contra el hash BCrypt almacenado.
    - Verifica que el usuario esté activo.
    - Devuelve el `access_token` JWT con tiempo de expiración.
    """
    user = db.query(User).filter(User.username == credentials.username).first()

    if not user or not verify_password(credentials.password, user.hashed_password):
        logger.warning(f"[Login Failed] Intento de login fallido para usuario: {credentials.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not user.is_active:
        logger.warning(f"[Login Disabled] Usuario inactivo intentó ingresar: {credentials.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Bearer"}
        )

    expires_minutes = settings.JWT_EXPIRATION_MINUTES
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "username": user.username,
            "role": user.role
        },
        expires_delta=timedelta(minutes=expires_minutes)
    )

    logger.info(f"[Login Success] Usuario autenticado exitosamente: {user.username} (Rol: {user.role})")

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_minutes * 60
    )


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener perfil del usuario autenticado"
)
async def get_me(current_user: User = Depends(get_current_user)):
    """
    Retorna la información del usuario autenticado en la sesión actual.
    No devuelve contraseñas ni secretos.
    """
    return UserResponse(
        id=str(current_user.id),
        username=current_user.username,
        role=current_user.role,
        is_active=current_user.is_active
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Renovar access token JWT"
)
async def refresh_token(
    request_data: Optional[RefreshTokenInput] = None,
    current_user: User = Depends(get_current_user)
):
    """
    Genera un nuevo token de acceso para un usuario actualmente autenticado.
    """
    expires_minutes = settings.JWT_EXPIRATION_MINUTES
    new_token = create_access_token(
        data={
            "sub": str(current_user.id),
            "username": current_user.username,
            "role": current_user.role
        },
        expires_delta=timedelta(minutes=expires_minutes)
    )

    return TokenResponse(
        access_token=new_token,
        token_type="bearer",
        expires_in=expires_minutes * 60
    )
