from typing import Optional
from pydantic import BaseModel, Field


class LoginInput(BaseModel):
    username: str = Field(..., description="Nombre de usuario registrado en el sistema")
    password: str = Field(..., description="Contraseña en texto plano para verificación")


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT Access Token firmado")
    token_type: str = Field("bearer", description="Tipo de token Bearer")
    expires_in: int = Field(..., description="Tiempo de validez en segundos")


class UserResponse(BaseModel):
    id: str = Field(..., description="Identificador único del usuario")
    username: str = Field(..., description="Nombre de usuario")
    role: str = Field(..., description="Rol asignado: Admin o User")
    is_active: bool = Field(True, description="Estado de activación de la cuenta")


class UserCreateInput(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Nombre de usuario único")
    password: str = Field(..., min_length=6, description="Contraseña segura")
    role: str = Field("User", description="Rol asignado ('Admin' o 'User')")


class RefreshTokenInput(BaseModel):
    token: Optional[str] = Field(None, description="Token JWT actual a renovar")
