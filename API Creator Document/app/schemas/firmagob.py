from typing import List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field


# --- Submodelos para Petición de Firma ---

class SenderModel(BaseModel):
    userCode: str = Field(..., description="Cédula o código de usuario firmante en OGTIC")
    entityCode: str = Field(default="default", description="Código de la entidad institucional")


class UserEntityModel(BaseModel):
    userCode: str = Field(..., description="Código de usuario destinatario")
    entityCode: str = Field(default="default", description="Código de la entidad")
    action: str = Field(default="SIGN", description="Acción a realizar: SIGN")


class AddresseeGroupModel(BaseModel):
    isOrGroup: bool = Field(default=False)
    userEntities: List[UserEntityModel] = Field(default_factory=list)


class AddresseeLineModel(BaseModel):
    addresseeGroups: List[AddresseeGroupModel] = Field(default_factory=list)


class VerificationAccessModel(BaseModel):
    type: str = Field(default="ANONYMOUS")


class StampPositionModel(BaseModel):
    page: int = 1
    x: float = 340.0
    y: float = 80.0
    height: float = 46.0
    width: float = 180.0
    userCode: Optional[str] = None
    entityCode: Optional[str] = None


class DocumentToSignModel(BaseModel):
    filename: str = Field(..., description="Nombre del archivo con extensión .pdf")
    data: str = Field(..., description="Contenido del documento PDF limpio en Base64")
    stampPositions: Optional[List[StampPositionModel]] = Field(default=None, description="Coordenadas para la estampa visual")


# --- Schema Principal de Entrada (JSON exacto recibido por la API) ---

class SignatureRequestInput(BaseModel):
    sender: SenderModel
    addresseeLines: List[AddresseeLineModel]
    internalNotification: Optional[List[Any]] = Field(default_factory=list)
    subject: str = Field(..., description="Asunto de la solicitud de firma")
    message: Optional[str] = Field(default="", description="Mensaje descriptivo")
    reference: Optional[str] = Field(default="", description="Número de expediente o referencia interna")
    verificationAccess: Optional[VerificationAccessModel] = Field(
        default_factory=lambda: VerificationAccessModel(type="ANONYMOUS")
    )
    senderNotificationLevel: Optional[str] = Field(default="ALL")
    signatureLevel: Optional[str] = Field(default="ALL")
    notificationUrl: Optional[str] = Field(
        default=None,
        description="URL directa del webhook callback. Si viene vacía, se inyecta la configurada en .env"
    )
    callbackCode: Optional[str] = Field(
        default="",
        description="Código de callback registrado en Firma GOB"
    )
    useDefaultStamp: Optional[bool] = Field(default=True)
    documentsToSign: List[DocumentToSignModel]


# --- Respuestas de Firma GOB (Viafirma Inbox v3) ---

class FirmaGobDocumentItem(BaseModel):
    code: str
    filename: str
    status: str = "NOT_SIGNED"


class FirmaGobCreateResponse(BaseModel):
    code: str
    publicAccessId: str
    status: str = "IN_PROCESS"
    documents: List[FirmaGobDocumentItem]


# --- Payload del Callback (Webhook de OGTIC) ---

class CallbackPayload(BaseModel):
    publicAccessId: str = Field(..., description="Identificador público de acceso para asociar el trámite")
    action: str = Field(..., description="Acción ejecutada: SIGN, APPROVAL, REJECT, EXPIRE, DELETE")
    status: str = Field(..., description="Estado del flujo: IN_PROCESS, COMPLETED, REJECTED, EXPIRED")
    callbackCode: Optional[str] = Field(default=None, description="Código o secreto de autenticación de callback")



class CallbackResponse(BaseModel):
    result: str = "ok"


# --- Respuesta de Estado para la Aplicación Cliente ---

class SignatureRequestDetailResponse(BaseModel):
    id: str
    reference: Optional[str]
    subject: Optional[str]
    status: str
    firmagob_code: Optional[str]
    public_access_id: Optional[str]
    document_id: Optional[str]
    original_filename: Optional[str]
    has_signed_file: bool
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    error_message: Optional[str]
