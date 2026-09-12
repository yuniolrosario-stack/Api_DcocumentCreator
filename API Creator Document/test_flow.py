import io
import sys
import time
import base64
import asyncio
import httpx
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def generate_sample_pdf_base64() -> str:
    """Genera un PDF valido en memoria y lo devuelve codificado en Base64."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, 720, "REPUBLICA DOMINICANA")
    c.setFont("Helvetica-Bold", 12)
    c.drawString(100, 700, "ORGANO OFICIAL - RESOLUCION MINISTERIAL")
    c.setFont("Helvetica", 10)
    c.drawString(100, 660, "Expediente: EXP-2026-00981")
    c.drawString(100, 640, "Asunto: Aprobacion de tramite oficial mediante Firma Desatendida")
    c.drawString(100, 600, "Por medio del presente documento se certifica la validez legal del acto")
    c.drawString(100, 580, "administrativo emitido bajo los estandares de la Ley 126-02 de Comercio")
    c.drawString(100, 560, "Electronico y Firmas Digitales.")
    c.save()
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


async def run_integration_test():
    base_url = "http://127.0.0.1:8000"
    print("Iniciando prueba de integracion de Firma GOB con Autenticacion JWT...")

    async with httpx.AsyncClient() as client:
        # 1. Health check
        try:
            health_resp = await client.get(f"{base_url}/api/v1/health", timeout=5.0)
            assert health_resp.status_code == 200, f"Health check fallo: {health_resp.status_code}"
            print("[OK] Servidor en linea y saludable (GET /api/v1/health).")
        except Exception as e:
            print(f"[ERROR] No se pudo conectar al servidor en {base_url}: {e}")
            return False

        # 2. Login para obtener JWT
        print("\n--- Autenticando cliente en POST /api/v1/auth/login ---")
        login_resp = await client.post(f"{base_url}/api/v1/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert login_resp.status_code == 200, f"Fallo autenticacion login: {login_resp.text}"
        access_token = login_resp.json()["access_token"]
        auth_headers = {"Authorization": f"Bearer {access_token}"}
        print("[OK] Token JWT obtenido con exito para peticiones protegidas.")

        # 3. Generar PDF de prueba
        pdf_base64 = generate_sample_pdf_base64()

        # 4. Construir el payload exacto especificado por el usuario
        payload = {
            "sender": {
                "userCode": "40200000000",
                "entityCode": "default"
            },
            "addresseeLines": [
                {
                    "addresseeGroups": [
                        {
                            "isOrGroup": False,
                            "userEntities": [
                                {
                                    "userCode": "40200000000",
                                    "entityCode": "default",
                                    "action": "SIGN"
                                }
                            ]
                        }
                    ]
                }
            ],
            "internalNotification": [],
            "subject": "Firma Desatendida de Documento Oficial",
            "message": "Solicitud generada automaticamente para firma en servidor.",
            "reference": "EXP-2026-00981",
            "verificationAccess": {
                "type": "ANONYMOUS"
            },
            "senderNotificationLevel": "ALL",
            "signatureLevel": "ALL",
            "notificationUrl": "http://127.0.0.1:8000/api/v1/firmagob/callback",
            "callbackCode": "CALLBACK_INSTITUCIONAL_01",
            "useDefaultStamp": True,
            "documentsToSign": [
                {
                    "filename": "resolucion_oficial_prueba.pdf",
                    "data": pdf_base64
                }
            ]
        }

        print("\n--- Paso 1: Enviando peticion de firma desatendida a POST /api/v1/documents/sign ---")
        sign_resp = await client.post(f"{base_url}/api/v1/documents/sign", json=payload, headers=auth_headers, timeout=10.0)
        assert sign_resp.status_code == 201, f"Error en creacion: {sign_resp.text}"
        sign_data = sign_resp.json()
        tracking_id = sign_data["trackingId"]
        public_access_id = sign_data["firmagob"]["publicAccessId"]
        document_id = sign_data["firmagob"]["documentId"]
        print(f"[OK] Solicitud creada exitosamente!")
        print(f"  - Tracking ID interno: {tracking_id}")
        print(f"  - publicAccessId: {public_access_id}")
        print(f"  - documentId: {document_id}")

        # 5. Esperar a que el Mock HSM procese la firma y el Webhook Callback se complete
        print("\n--- Paso 2: Esperando notificacion asincrona del Webhook (Callback)... ---")
        max_retries = 10
        completed = False
        for attempt in range(max_retries):
            await asyncio.sleep(1)
            status_resp = await client.get(f"{base_url}/api/v1/documents/{tracking_id}", headers=auth_headers)
            status_data = status_resp.json()
            curr_status = status_data["status"]
            has_file = status_data["hasSignedFile"]
            print(f"  Intento {attempt + 1}: Estado = {curr_status}, Archivo Firmado = {has_file}")
            if curr_status == "COMPLETED" and has_file:
                completed = True
                break

        assert completed, "El tramite no alcanzo el estado COMPLETED en el tiempo esperado."
        print("[OK] Webhook recibido y procesado con exito. Estado final: COMPLETED.")

        # 6. Descargar documento firmado
        print("\n--- Paso 3: Descargando PDF firmado desde GET /api/v1/documents/{id}/download ---")
        download_resp = await client.get(f"{base_url}/api/v1/documents/{tracking_id}/download", headers=auth_headers)
        assert download_resp.status_code == 200, f"Fallo al descargar documento: {download_resp.status_code}"
        assert len(download_resp.content) > 100, "El documento descargado esta vacio."
        assert download_resp.content.startswith(b"%PDF"), "El archivo descargado no es un PDF valido."
        print(f"[OK] PDF firmado descargado con exito ({len(download_resp.content)} bytes).")

    print("\n" + "=" * 50)
    print("TODAS LAS PRUEBAS DE INTEGRACION PASARON EXITOSAMENTE!")
    print("=" * 50)
    return True


if __name__ == "__main__":
    asyncio.run(run_integration_test())
