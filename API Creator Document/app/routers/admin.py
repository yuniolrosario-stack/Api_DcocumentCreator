import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import User
from app.schemas.auth import UserResponse, UserCreateInput
from app.core.security import hash_password
from app.core.auth_dependencies import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["Administración de Usuarios"])


@router.get(
    "/users",
    response_model=List[UserResponse],
    status_code=status.HTTP_200_OK,
    summary="Listar usuarios del sistema (Requiere Rol Admin)"
)
def list_users(
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    """
    Retorna la lista de todos los usuarios registrados en el sistema.
    Exclusivo para administradores.
    """
    users = db.query(User).all()
    return [
        UserResponse(
            id=str(u.id),
            username=u.username,
            role=u.role,
            is_active=u.is_active
        )
        for u in users
    ]


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear nuevo usuario con rol asignado (Requiere Rol Admin)"
)
def create_user(
    user_in: UserCreateInput,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    """
    Registra un nuevo usuario en la base de datos con contraseña hasheada en BCrypt.
    Exclusivo para administradores.
    """
    existing = db.query(User).filter(User.username == user_in.username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El nombre de usuario '{user_in.username}' ya existe"
        )

    if user_in.role not in ("Admin", "User"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El rol debe ser 'Admin' o 'User'"
        )

    new_user = User(
        username=user_in.username,
        hashed_password=hash_password(user_in.password),
        role=user_in.role,
        is_active=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    logger.info(f"[Admin] Usuario creado exitosamente: {new_user.username} con rol {new_user.role}")

    return UserResponse(
        id=str(new_user.id),
        username=new_user.username,
        role=new_user.role,
        is_active=new_user.is_active
    )
