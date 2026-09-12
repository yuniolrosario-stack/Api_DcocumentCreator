import os
import json
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import SignatureRequest, User
from app.schemas.firmagob import (
    SignatureRequestInput,
    SignatureRequestDetailResponse
)
from app.services.firmagob_client import firmagob_client
from app.services.storage_service import storage_service
from app.core.config import settings
from app.core.auth_dependencies import get_current_user
from app.middleware.security import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/documents", tags=["Gestión de Firmas Desatendidas"])



@router.post(
    "/sign",
    summary="Crear Petición de Firma Desatendida (Recibe JSON oficial)",
    status_code=status.HTTP_201_CREATED
)
async def create_signature_request(
    payload: SignatureRequestInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Recibe el payload JSON exacto para iniciar el trámite de firma desatendida.
    1. Valida y guarda el PDF original en disco.
    2. Registra la petición en la base de datos local.
    3. Envía la solicitud a Firma GOB (Endpoint 1: POST /api/v3/requests).
    4. Guarda los identificadores retornados (code, publicAccessId, documentId).
    """
    if not payload.documentsToSign:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe incluir al menos un documento en 'documentsToSign'"
        )

    first_doc = payload.documentsToSign[0]
    
    if first_doc.data == "{{document}}" or len(first_doc.data.strip()) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El campo 'data' debe contener una cadena válida en Base64 del archivo PDF a firmar."
        )

    # 1. Guardar PDF original en almacenamiento local
    try:
        saved_orig_path, _ = storage_service.save_base64_file(
            base64_data=first_doc.data,
            filename=first_doc.filename,
            subfolder="original"
        )
    except Exception as e:
        logger.error(f"Error decodificando Base64: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error decodificando el documento Base64: {str(e)}"
        )

    # 2. Extraer datos para registro en BD
    sender_user = payload.sender.userCode if payload.sender else None
    sender_entity = payload.sender.entityCode if payload.sender else "default"

    addressee_user = None
    addressee_entity = "default"
    addressee_action = "SIGN"

    if payload.addresseeLines:
        line = payload.addresseeLines[0]
        if line.addresseeGroups and line.addresseeGroups[0].userEntities:
            first_user = line.addresseeGroups[0].userEntities[0]
            addressee_user = first_user.userCode
            addressee_entity = first_user.entityCode
            addressee_action = first_user.action

    # Preparar el payload a enviar a Firma GOB
    payload_dict = payload.model_dump()

    if not payload_dict.get("callbackCode") and settings.FIRMAGOB_CALLBACK_CODE:
        payload_dict["callbackCode"] = settings.FIRMAGOB_CALLBACK_CODE

    if not payload_dict.get("notificationUrl") and settings.CALLBACK_URL:
        payload_dict["notificationUrl"] = settings.CALLBACK_URL

    # Registrar en BD estado inicial PENDING
    db_request = SignatureRequest(
        reference=payload.reference,
        subject=payload.subject,
        message=payload.message,
        sender_user_code=sender_user,
        sender_entity_code=sender_entity,
        addressee_user_code=addressee_user,
        addressee_entity_code=addressee_entity,
        addressee_action=addressee_action,
        original_filename=first_doc.filename,
        original_file_path=saved_orig_path,
        status="PENDING",
        raw_request=json.dumps(payload_dict)
    )
    db.add(db_request)
    db.commit()
    db.refresh(db_request)

    # 3. Llamar a Firma GOB (Endpoint 1: POST /api/v3/requests)
    try:
        fg_response = await firmagob_client.create_request(payload_dict)
    except Exception as e:
        logger.error(f"Error comunicándose con Firma GOB: {e}", exc_info=True)
        db_request.status = "ERROR"
        db_request.error_message = str(e)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error en comunicación con Firma GOB: {str(e)}"
        )

    # 4. Actualizar con los códigos devueltos por Firma GOB / Viafirma
    code = fg_response.get("code") or fg_response.get("publicAccessId")
    public_access_id = fg_response.get("publicAccessId") or fg_response.get("code")

    # Extraer ID del documento (soporta 'documentsToSign' y 'documents', con 'publicAccessId' o 'code')
    docs_list = fg_response.get("documentsToSign") or fg_response.get("documents", [])
    document_id = None
    if docs_list and isinstance(docs_list, list):
        first_item = docs_list[0]
        document_id = first_item.get("publicAccessId") or first_item.get("code")

    db_request.firmagob_code = code
    db_request.public_access_id = public_access_id
    db_request.document_id = document_id
    db_request.status = "IN_PROCESS"
    db_request.raw_response = json.dumps(fg_response)
    db.commit()
    db.refresh(db_request)

    logger.info(
        f"Solicitud {db_request.id} creada en Firma GOB con éxito. "
        f"publicAccessId={public_access_id}, documentId={document_id}"
    )

    return {
        "success": True,
        "message": "Solicitud de firma desatendida registrada en Firma GOB con éxito.",
        "trackingId": db_request.id,
        "reference": db_request.reference,
        "firmagob": {
            "code": code,
            "publicAccessId": public_access_id,
            "documentId": document_id,
            "status": "IN_PROCESS"
        },
        "nextSteps": "Firma GOB procesará la firma asíncronamente y notificará al webhook configurado."
    }


@router.get("", summary="Listar solicitudes de firma")
def list_signature_requests(
    status_filter: Optional[str] = Query(None, alias="status", description="Filtrar por estado"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(SignatureRequest)
    if status_filter:
        query = query.filter(SignatureRequest.status == status_filter.upper())

    total = query.count()
    items = query.order_by(SignatureRequest.created_at.desc()).offset(skip).limit(limit).all()

    result = []
    for item in items:
        result.append({
            "id": item.id,
            "reference": item.reference,
            "subject": item.subject,
            "status": item.status,
            "publicAccessId": item.public_access_id,
            "documentId": item.document_id,
            "originalFilename": item.original_filename,
            "hasSignedFile": bool(item.signed_file_path and os.path.exists(item.signed_file_path)),
            "createdAt": item.created_at.isoformat() if item.created_at else None,
            "updatedAt": item.updated_at.isoformat() if item.updated_at else None
        })

    return {
        "total": total,
        "items": result
    }


@router.get("/{tracking_id}", summary="Consultar estado de una solicitud")
def get_signature_request_detail(
    tracking_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    req = db.query(SignatureRequest).filter(SignatureRequest.id == tracking_id).first()
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Solicitud de firma no encontrada"
        )

    has_signed = bool(req.signed_file_path and os.path.exists(req.signed_file_path))

    return {
        "id": req.id,
        "reference": req.reference,
        "subject": req.subject,
        "message": req.message,
        "sender": {
            "userCode": req.sender_user_code,
            "entityCode": req.sender_entity_code
        },
        "addressee": {
            "userCode": req.addressee_user_code,
            "entityCode": req.addressee_entity_code,
            "action": req.addressee_action
        },
        "status": req.status,
        "firmagobCode": req.firmagob_code,
        "publicAccessId": req.public_access_id,
        "documentId": req.document_id,
        "originalFilename": req.original_filename,
        "hasSignedFile": has_signed,
        "signedFilePath": req.signed_file_path if has_signed else None,
        "createdAt": req.created_at.isoformat() if req.created_at else None,
        "updatedAt": req.updated_at.isoformat() if req.updated_at else None,
        "errorMessage": req.error_message
    }


@router.get("/{tracking_id}/download", summary="Descargar documento (Firmado si está listo, u Original)")
def download_document(
    tracking_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    req = db.query(SignatureRequest).filter(SignatureRequest.id == tracking_id).first()
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Solicitud no encontrada"
        )

    if req.signed_file_path and os.path.exists(req.signed_file_path):
        filename = f"FIRMADO_{req.original_filename or 'documento.pdf'}"
        return FileResponse(
            path=req.signed_file_path,
            filename=filename,
            media_type="application/pdf"
        )
    elif req.original_file_path and os.path.exists(req.original_file_path):
        filename = f"ORIGINAL_{req.original_filename or 'documento.pdf'}"
        return FileResponse(
            path=req.original_file_path,
            filename=filename,
            media_type="application/pdf"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El archivo físico no se encuentra disponible en el servidor"
        )
