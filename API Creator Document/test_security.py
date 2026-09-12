import sys
import json
import asyncio
import httpx
from fastapi.testclient import TestClient

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from app.main import app
from app.core.config import settings
from app.db.session import engine, Base
from app.db.models import User, SignatureRequest


def test_suite_security():
    print("\n" + "=" * 60)
    print(" EJECUTANDO SUITE DE PRUEBAS DE SEGURIDAD Y VÍA FIRMA GOB")
    print("=" * 60 + "\n")

    # Asegurar creación de todas las tablas en BD
    Base.metadata.create_all(bind=engine)

    with TestClient(app) as client:
        # -------------------------------------------------------------
        # PRUEBA 1: Login Correcto
        # -------------------------------------------------------------
        print("--- Prueba 1: Login correcto con username + password ---")
        login_resp = client.post("/api/v1/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert login_resp.status_code == 200, f"Error en login: {login_resp.text}"
        login_data = login_resp.json()
        assert "access_token" in login_data, "No se recibió access_token"
        token = login_data["access_token"]
        print(f"[OK] Login exitoso. JWT generado ({len(token)} chars).")

        # -------------------------------------------------------------
        # PRUEBA 2: Password Incorrecto
        # -------------------------------------------------------------
        print("\n--- Prueba 2: Password incorrecto ---")
        bad_login_resp = client.post("/api/v1/auth/login", json={
            "username": "admin",
            "password": "wrong_password_123"
        })
        assert bad_login_resp.status_code == 401, f"Se esperaba 401, pero fue: {bad_login_resp.status_code}"
        print("[OK] Retornó 401 Unauthorized correctamente.")

        # -------------------------------------------------------------
        # PRUEBA 3: Endpoint Privado sin JWT
        # -------------------------------------------------------------
        print("\n--- Prueba 3: Endpoint privado sin JWT ---")
        no_jwt_resp = client.get("/api/v1/documents")
        assert no_jwt_resp.status_code == 401, f"Se esperaba 401, pero fue: {no_jwt_resp.status_code}"
        print("[OK] Retornó 401 Unauthorized al acceder sin token.")

        # -------------------------------------------------------------
        # PRUEBA 4: Endpoint Privado con JWT Válido
        # -------------------------------------------------------------
        print("\n--- Prueba 4: Endpoint privado con JWT válido ---")
        jwt_resp = client.get("/api/v1/documents", headers={"Authorization": f"Bearer {token}"})
        assert jwt_resp.status_code == 200, f"Se esperaba 200, pero fue: {jwt_resp.status_code}"
        print("[OK] Acceso concedido con JWT válido.")

        # -------------------------------------------------------------
        # PRUEBA 5: Usuario sin Permisos Administrativos (Rol User)
        # -------------------------------------------------------------
        print("\n--- Prueba 5: Usuario común sin permisos de Admin ---")
        # 1. Crear usuario común como Admin
        create_user_resp = client.post("/api/v1/admin/users", json={
            "username": "common_user",
            "password": "user12345",
            "role": "User"
        }, headers={"Authorization": f"Bearer {token}"})
        assert create_user_resp.status_code in (201, 409), f"Error al crear usuario común: {create_user_resp.text}"

        # 2. Login como usuario común
        user_login_resp = client.post("/api/v1/auth/login", json={
            "username": "common_user",
            "password": "user12345"
        })
        user_token = user_login_resp.json()["access_token"]

        # 3. Intentar acceder a endpoint de administración con token de User
        forbidden_resp = client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {user_token}"})
        assert forbidden_resp.status_code == 403, f"Se esperaba 403, pero fue: {forbidden_resp.status_code}"
        print("[OK] Retornó 403 Forbidden para usuario sin rol Admin.")

        # -------------------------------------------------------------
        # PRUEBA 6: Rate Limiting en Login
        # -------------------------------------------------------------
        print("\n--- Prueba 6: Rate Limiting en Login ---")
        limit_hit = False
        for i in range(10):
            r = client.post("/api/v1/auth/login", json={"username": "fake", "password": "fake"})
            if r.status_code == 429:
                limit_hit = True
                print(f"[OK] Límite de tasa alcanzado en el intento {i + 1}. HTTP 429 Too Many Requests.")
                break
        assert limit_hit, "No se activó el Rate Limit en /auth/login tras múltiples intentos"

        # -------------------------------------------------------------
        # PRUEBA 7: Callback Viafirma Válido (Sin JWT de usuario)
        # -------------------------------------------------------------
        print("\n--- Prueba 7: Callback de Viafirma válido (Sin JWT de usuario) ---")
        cb_payload = {
            "publicAccessId": "PUB-TEST-0001",
            "action": "SIGN",
            "status": "COMPLETED",
            "callbackCode": settings.FIRMAGOB_CALLBACK_CODE
        }
        cb_resp = client.post("/api/v1/firmagob/callback", json=cb_payload)
        assert cb_resp.status_code == 200, f"Error en callback válido: {cb_resp.text}"
        assert cb_resp.json()["result"] == "ok"
        print("[OK] Callback procesado exitosamente sin JWT de usuario.")

        # -------------------------------------------------------------
        # PRUEBA 8: Callback Viafirma con Autenticación Inválida
        # -------------------------------------------------------------
        print("\n--- Prueba 8: Callback Viafirma con secreto inválido ---")
        bad_cb_payload = {
            "publicAccessId": "PUB-TEST-0001",
            "action": "SIGN",
            "status": "COMPLETED",
            "callbackCode": "WRONG_SECRET_CODE"
        }
        bad_cb_resp = client.post("/api/v1/firmagob/callback", json=bad_cb_payload)
        assert bad_cb_resp.status_code == 401, f"Se esperaba 401 en callback inválido, pero fue: {bad_cb_resp.status_code}"
        print("[OK] Retornó 401 Unauthorized al enviar secreto de callback incorrecto.")

        # -------------------------------------------------------------
        # PRUEBA 9: Idempotencia de Callback
        # -------------------------------------------------------------
        print("\n--- Prueba 9: Idempotencia de Callbacks Duplicados ---")
        cb_dup_resp = client.post("/api/v1/firmagob/callback", json=cb_payload)
        assert cb_dup_resp.status_code == 200, f"Error en callback idempotente: {cb_dup_resp.text}"
        print("[OK] Notificación duplicada aceptada con 200 OK (Idempotente).")

        # -------------------------------------------------------------
        # PRUEBA 10: Health Check Público
        # -------------------------------------------------------------
        print("\n--- Prueba 10: Health Check Público ---")
        health_resp = client.get("/api/v1/health")
        assert health_resp.status_code == 200
        assert health_resp.json() == {"status": "healthy"}
        print("[OK] GET /api/v1/health funcional y público.")

    print("\n" + "=" * 60)
    print(" TODAS LAS PRUEBAS DE SEGURIDAD PASARON CON ÉXITO!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    test_suite_security()
