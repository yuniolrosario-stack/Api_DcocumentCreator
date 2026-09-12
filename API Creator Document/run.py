import sys
import uvicorn
from app.core.config import settings

# Asegurar compatibilidad UTF-8 en terminal de Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

if __name__ == "__main__":
    print("=" * 65)
    print("Iniciando API Integracion Firma GOB / OGTIC (Viafirma Inbox v3)")
    print(f"Documentacion Swagger: http://127.0.0.1:{settings.APP_PORT}/docs")
    print(f"Dashboard Interactivo: http://127.0.0.1:{settings.APP_PORT}/")
    print(f"Modo Mock OGTIC: {'ACTIVADO' if settings.ENABLE_MOCK_OGTIC else 'DESACTIVADO'}")
    print(f"Endpoint Callback Webhook: {settings.CALLBACK_URL}")
    print("=" * 65)
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=False
    )
