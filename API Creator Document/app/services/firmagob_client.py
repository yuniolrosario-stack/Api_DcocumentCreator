import base64
import logging
from typing import Dict, Any
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


class FirmaGobClient:
    def __init__(self):
        self.base_url = settings.FIRMAGOB_BASE_URL.rstrip("/")
        self.auth = (settings.FIRMAGOB_USER, settings.FIRMAGOB_PASSWORD)
        self.timeout = httpx.Timeout(30.0, connect=10.0)

    async def create_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Paso 1: POST /api/v3/requests
        Envía la solicitud de firma desatendida a Firma GOB (OGTIC / Viafirma).
        """
        endpoint = f"{self.base_url}/api/v3/requests"
        logger.info(f"Enviando solicitud de firma desatendida a {endpoint}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                endpoint,
                json=payload,
                auth=self.auth,
                headers={"Content-Type": "application/json"}
            )

            if response.status_code not in (200, 201):
                logger.error(
                    f"Error de Firma GOB ({response.status_code}): {response.text}"
                )
                raise RuntimeError(
                    f"Firma GOB respondió con HTTP {response.status_code}: {response.text}"
                )

            return response.json()

    async def download_signed_document(self, document_id: str) -> bytes:
        """
        Paso 3: GET /api/v3/documents/{documentId}/signed
        Descarga el documento con las firmas electrónicas incrustadas.
        Soporta respuesta binaria PDF directa o JSON con campo Base64 'data'.
        """
        endpoint = f"{self.base_url}/api/v3/documents/{document_id}/signed"
        logger.info(f"Descargando documento firmado desde {endpoint}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                endpoint,
                auth=self.auth
            )

            if response.status_code != 200:
                logger.error(
                    f"Error al descargar documento firmado ({response.status_code}): {response.text}"
                )
                raise RuntimeError(
                    f"Firma GOB respondió con HTTP {response.status_code} al descargar documento"
                )

            content_type = response.headers.get("content-type", "").lower()

            # Caso 1: JSON con data Base64
            if "application/json" in content_type:
                try:
                    data_json = response.json()
                    if "data" in data_json:
                        return base64.b64decode(data_json["data"])
                except Exception as e:
                    logger.warning(f"Error interpretando JSON en descarga: {e}")

            # Caso 2: Binario PDF directo (application/pdf o octet-stream)
            return response.content


firmagob_client = FirmaGobClient()
