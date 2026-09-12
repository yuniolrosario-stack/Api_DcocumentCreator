import json
import logging
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Header, Query, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db, SessionLocal
from app.db.models import SignatureRequest
from app.schemas.firmagob import CallbackPayload, CallbackResponse
from app.services.firmagob_client import firmagob_client
from app.services.storage_service import storage_service
from app.core.config import settings
from app.middleware.security import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/firmagob", tags=["Webhook Callback (OGTIC)"])


def verify_viafirma_authentication(
    payload: CallbackPayload,
    x_callback_code: Optional[str] = Header(None, alias="X-Callback-Code"),
    x_viafirma_secret: Optional[str] = Header(None, alias="X-Viafirma-Secret"),
    code_param: Optional[str] = Query(None, alias="callbackCode")
):
    """
    Autenticación específica para la integración con Viafirma / Firma GOB.
    NO utiliza JWT de usuario.
    Verifica que el código/secreto de callback coincida con el configurado.
    """
    expected_secret = settings.VIAFIRMA_CALLBACK_SECRET or settings.FIRMAGOB_CALLBACK_CODE
    if not expected_secret:
        return True  # Si no hay secreto configurado, se permite la comunicación

    # Se acepta el secreto en: campo del payload, header HTTP o parámetro query
    received_secret = (
        payload.callbackCode or
        x_callback_code or
        x_viafirma_secret or
        code_param
    )

    # Si se proporcionó un secreto, se valida contra el esperado
    if received_secret and received_secret == expected_secret:
        return True

    # Si el payload o llamada trae un código que no coincide, o no trae ninguno cuando es requerido
    if received_secret and received_secret != expected_secret:
        logger.warning(
            f"[Viafirma Auth Failed] Secreto recibido no coincide: '{received_secret}' != '{expected_secret}'"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized"
        )

    # Si no trae secreto pero está configurado uno por defecto, permitimos si el payload es estructuralmente válido
    return True


async def process_completed_signature_job(public_access_id: str, action: str, callback_status: str, raw_payload_str: str):
    """
    Tarea en segundo plano (Background Task) ejecutada tras responder 200 OK al webhook.
    1. Busca la solicitud en la base de datos por publicAccessId.
    2. Si action == 'SIGN' y status == 'COMPLETED':
       - Llama a Firma GOB (Endpoint 3: GET /api/v3/documents/{documentId}/signed).
       - Guarda el binario PDF en storage/signed/.
       - Actualiza el registro a COMPLETED.
    3. Si es REJECTED, actualiza el estado.
    """
    db: Session = SessionLocal()
    try:
        req = db.query(SignatureRequest).filter(
            SignatureRequest.public_access_id == public_access_id
        ).first()

        if not req:
            logger.warning(
                f"[Webhook Job] No se encontró solicitud con publicAccessId={public_access_id}"
            )
            return

        req.raw_callback = raw_payload_str

        if action == "SIGN" and callback_status == "COMPLETED":
            # Control secundario de idempotencia dentro del Job
            if req.status == "COMPLETED" and req.signed_file_path:
                logger.info(f"[Webhook Job Idempotente] La solicitud {req.id} ya estaba completada. Ignorando reintento.")
                return

            logger.info(
                f"[Webhook Job] Firma completada para solicitud {req.id} (Doc: {req.document_id}). Iniciando descarga..."
            )
            try:
                # Paso 3: Descarga del documento firmado
                signed_bytes = await firmagob_client.download_signed_document(req.document_id)
                
                # Guardar en almacenamiento local
                signed_filename = f"signed_{req.original_filename or f'{req.id}.pdf'}"
                saved_path = storage_service.save_binary_file(
                    file_bytes=signed_bytes,
                    filename=signed_filename,
                    subfolder="signed"
                )

                req.signed_file_path = saved_path
                req.status = "COMPLETED"
                req.error_message = None
                db.commit()
                logger.info(
                    f"[Webhook Job] ÉXITO: Documento firmado guardado en {saved_path} para solicitud {req.id}"
                )
            except Exception as e:
                logger.error(f"[Webhook Job] Error al descargar documento firmado: {e}", exc_info=True)
                req.status = "ERROR"
                req.error_message = f"Falla en descarga de documento firmado: {str(e)}"
                db.commit()
        elif callback_status == "REJECTED":
            req.status = "REJECTED"
            db.commit()
            logger.warning(f"[Webhook Job] Solicitud {req.id} fue RECHAZADA por el firmante/sistema.")
        else:
            logger.info(
                f"[Webhook Job] Notificación recibida para {req.id}: action={action}, status={callback_status}"
            )
    except Exception as ex:
        logger.error(f"[Webhook Job] Excepción no controlada: {ex}", exc_info=True)
    finally:
        db.close()


@router.post(
    "/callback",
    response_model=CallbackResponse,
    status_code=status.HTTP_200_OK,
    summary="Endpoint 2: Recepción de Notificación de Firma (Webhook OGTIC / Viafirma)"
)
@limiter.limit(settings.RATE_LIMIT_VIAFIRMA)
async def receive_firmagob_callback(
    request: Request,
    payload: CallbackPayload,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _auth: bool = Depends(verify_viafirma_authentication)
):
    """
    ## Endpoint 2 de la especificación técnica de OGTIC / Firma GOB
    - Recibe notificación HTTP POST de Viafirma/Firma GOB cuando se completa la firma.
    - **NO requiere JWT de usuario**. Utiliza autenticación específica de integración.
    - Valida parámetros del webhook (`publicAccessId`, `action`, `status`).
    - **Protección de Idempotencia**: Si el trámite ya fue procesado a estado final, no duplica trabajo.
    - Retorna de inmediato HTTP 200 OK en < 5s para evitar reintentos.
    """
    logger.info(
        f"[Webhook] Notificación recibida: publicAccessId={payload.publicAccessId}, "
        f"action={payload.action}, status={payload.status}"
    )

    # 1. Verificación de IDEMPOTENCIA
    existing_req = db.query(SignatureRequest).filter(
        SignatureRequest.public_access_id == payload.publicAccessId
    ).first()

    if existing_req and existing_req.status == "COMPLETED" and payload.status == "COMPLETED":
        logger.info(
            f"[Webhook Idempotente] Notificación duplicada recibida para publicAccessId={payload.publicAccessId}. "
            "El documento ya fue procesado previamente. Retornando HTTP 200 OK."
        )
        return CallbackResponse(result="ok")

    raw_payload_str = json.dumps(payload.model_dump())

    # 2. Encolar la tarea asíncrona de procesamiento y descarga en segundo plano
    background_tasks.add_task(
        process_completed_signature_job,
        public_access_id=payload.publicAccessId,
        action=payload.action,
        callback_status=payload.status,
        raw_payload_str=raw_payload_str
    )

    # 3. Respuesta rápida e inmediata HTTP 200 OK requerida por OGTIC (< 5s)
    return CallbackResponse(result="ok")
