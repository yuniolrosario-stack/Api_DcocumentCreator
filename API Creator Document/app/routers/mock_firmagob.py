import io
import time
import uuid
import asyncio
import logging
from typing import Dict, Any
from fastapi import APIRouter, BackgroundTasks, HTTPException, Response, status
import httpx
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from pypdf import PdfReader, PdfWriter

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mock-ogtic/api/v3", tags=["Simulador OGTIC / Viafirma (Mock)"])

_MOCK_DOCS: Dict[str, Dict[str, Any]] = {}


async def _simulate_hsm_signature_and_callback(public_access_id: str, callback_url: str, delay_seconds: int):
    """
    Simula el retardo del HSM de firma desatendida en OGTIC
    y luego dispara el Webhook Callback a la URL del cliente.
    """
    await asyncio.sleep(delay_seconds)

    payload = {
        "publicAccessId": public_access_id,
        "action": "SIGN",
        "status": "COMPLETED"
    }

    logger.info(f"[Mock OGTIC] HSM completó la firma. Disparando webhook a {callback_url}...")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(callback_url, json=payload)
            logger.info(f"[Mock OGTIC] Webhook entregado con éxito a {callback_url}. Respuesta: {resp.status_code}")
    except Exception as e:
        logger.error(f"[Mock OGTIC] Error al entregar webhook a {callback_url}: {e}")


def _generate_stamped_pdf(original_pdf_bytes: bytes, user_code: str, reference: str) -> bytes:
    """
    Estampa un sello visual de firma digital PAdES / Firma GOB sobre el PDF.
    """
    try:
        reader = PdfReader(io.BytesIO(original_pdf_bytes))
        writer = PdfWriter()

        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=letter)
        can.setStrokeColorRGB(0, 0.35, 0.65)
        can.setFillColorRGB(0.95, 0.97, 1.0)
        can.rect(320, 50, 240, 65, fill=1, stroke=1)

        can.setFillColorRGB(0, 0.25, 0.5)
        can.setFont("Helvetica-Bold", 8)
        can.drawString(330, 100, "FIRMA DIGITAL CUALIFICADA - FIRMA GOB")
        can.setFont("Helvetica", 7)
        can.setFillColorRGB(0.1, 0.1, 0.1)
        can.drawString(330, 88, f"Firmante: {user_code} (Certificado en Servidor)")
        can.drawString(330, 76, f"Ref / Expediente: {reference}")
        can.drawString(330, 64, f"Fecha: {time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        can.setFillColorRGB(0, 0.5, 0.2)
        can.drawString(330, 54, "ESTADO: VALIDO - TS (Sello de Tiempo)")
        can.save()

        packet.seek(0)
        stamp_pdf = PdfReader(packet)
        stamp_page = stamp_pdf.pages[0]

        for i, page in enumerate(reader.pages):
            if i == 0:
                page.merge_page(stamp_page)
            writer.add_page(page)

        output_stream = io.BytesIO()
        writer.write(output_stream)
        return output_stream.getvalue()
    except Exception as e:
        logger.warning(f"[Mock OGTIC] No se pudo fusionar estampa en PDF: {e}. Retornando original.")
        return original_pdf_bytes


@router.post("/requests", summary="Mock OGTIC: Crear Petición de Firma Desatendida")
async def mock_create_request(payload: Dict[str, Any], background_tasks: BackgroundTasks):
    """
    Simula el Endpoint 1 de Firma GOB:
    - Genera code y publicAccessId.
    - Registra el documento en memoria temporal.
    - Programa el callback automático tras MOCK_SIGN_DELAY_SECONDS.
    """
    code = f"MOCK-{uuid.uuid4().hex[:8].upper()}"
    public_access_id = f"PAID-{uuid.uuid4().hex[:12].upper()}"
    doc_code = f"DOC-{uuid.uuid4().hex[:8].upper()}"

    docs_to_sign = payload.get("documentsToSign", [])
    first_filename = docs_to_sign[0].get("filename", "documento.pdf") if docs_to_sign else "documento.pdf"
    first_data = docs_to_sign[0].get("data", "") if docs_to_sign else ""

    callback_url = payload.get("notificationUrl") or settings.CALLBACK_URL

    _MOCK_DOCS[doc_code] = {
        "filename": first_filename,
        "base64_data": first_data,
        "user_code": payload.get("sender", {}).get("userCode", "00000000000"),
        "reference": payload.get("reference", "REF-001"),
        "public_access_id": public_access_id,
        "status": "COMPLETED"
    }

    background_tasks.add_task(
        _simulate_hsm_signature_and_callback,
        public_access_id=public_access_id,
        callback_url=callback_url,
        delay_seconds=settings.MOCK_SIGN_DELAY_SECONDS
    )

    return {
        "code": code,
        "publicAccessId": public_access_id,
        "status": "IN_PROCESS",
        "documents": [
            {
                "code": doc_code,
                "filename": first_filename,
                "status": "NOT_SIGNED"
            }
        ]
    }


@router.get("/documents/{document_id}/signed", summary="Mock OGTIC: Descargar PDF Firmado")
async def mock_download_signed(document_id: str):
    """
    Simula el Endpoint 3 de Firma GOB:
    - Retorna el PDF firmado con sello digital y marca visual.
    """
    import base64

    doc_info = _MOCK_DOCS.get(document_id)
    if not doc_info:
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        c.drawString(100, 700, f"Documento firmado de prueba - ID: {document_id}")
        c.drawString(100, 680, "Firma GOB OGTIC Mock Server - Certificado Cualificado")
        c.save()
        original_bytes = buffer.getvalue()
        user_code = "40200000000"
        reference = "MOCK-DOC"
    else:
        try:
            original_bytes = base64.b64decode(doc_info["base64_data"])
        except Exception:
            original_bytes = b"%PDF-1.4 Mock Empty PDF"
        user_code = doc_info.get("user_code", "40200000000")
        reference = doc_info.get("reference", "REF-001")

    signed_bytes = _generate_stamped_pdf(original_bytes, user_code, reference)

    return Response(
        content=signed_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="firmado_{document_id}.pdf"'
        }
    )
