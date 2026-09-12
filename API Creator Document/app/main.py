import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.openapi.utils import get_openapi
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.db.session import engine, Base, SessionLocal
from app.db.models import User
from app.core.security import hash_password
from app.routers import documents, callback, mock_firmagob, auth, admin
from app.middleware.security import (
    limiter,
    SecurityHeadersMiddleware,
    rate_limit_exceeded_handler,
    global_exception_handler
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Inicializar tablas en base de datos SQLite
    Base.metadata.create_all(bind=engine)

    # 2. Inicializar directorios de almacenamiento
    _ = settings.storage_path

    # 3. Sembrar usuario administrador inicial si la base de datos no contiene usuarios
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            default_admin = User(
                username="admin",
                hashed_password=hash_password("admin123"),
                role="Admin",
                is_active=True
            )
            db.add(default_admin)
            db.commit()
            logger.info("[Startup] Usuario administrador inicial creado ('admin' / 'admin123')")
    except Exception as e:
        logger.error(f"[Startup Error] Error sembrando usuario inicial: {e}")
    finally:
        db.close()

    yield


app = FastAPI(
    title="API Integración Firma Desatendida & Callback (OGTIC / Firma GOB)",
    description=(
        "Servicio backend seguro para la integración de firma en servidor (sello electrónico) "
        "y notificaciones asíncronas vía webhook con la plataforma Firma GOB (Viafirma Inbox v3)."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Integración del Rate Limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# Manejador global de excepciones para evitar filtrado de información sensible
app.add_exception_handler(Exception, global_exception_handler)

# Middleware de Seguridad HTTP (Headers)
app.add_middleware(SecurityHeadersMiddleware)

# CORS Middleware con orígenes configurados
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Registrar Routers
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(documents.router)
app.include_router(callback.router)

if settings.ENABLE_MOCK_OGTIC:
    app.include_router(mock_firmagob.router)


@app.get("/api/v1/health", tags=["Salud del Servicio"], status_code=status.HTTP_200_OK)
@app.get("/api/health", tags=["Salud del Servicio"], status_code=status.HTTP_200_OK)
def health_check():
    """
    Endpoint público de verificación de salud del servicio.
    No expone contraseñas, secretos, ni información interna sensible.
    """
    return {
        "status": "healthy"
    }


# Configuración Personalizada de OpenAPI para Autorización Bearer JWT en Swagger UI
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    if "components" not in openapi_schema:
        openapi_schema["components"] = {}

    openapi_schema["components"]["securitySchemes"] = {
        "HTTPBearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Ingrese el JWT devuelto por POST /api/v1/auth/login"
        }
    }

    # Aplicar seguridad Bearer global a las rutas (Swagger UI) excepto login, health y callback
    for path, path_item in openapi_schema["paths"].items():
        for method, operation in path_item.items():
            if method.lower() in ("get", "post", "put", "patch", "delete"):
                # Excluir autenticación de usuario en endpoints públicos / integración
                if path in ("/api/v1/auth/login", "/api/v1/health", "/api/health", "/api/v1/firmagob/callback"):
                    continue
                if path.startswith("/mock-ogtic"):
                    continue
                operation["security"] = [{"HTTPBearer": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


# Servir Dashboard estático si existe
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", include_in_schema=False)
    @app.get("/dashboard", include_in_schema=False)
    def serve_dashboard():
        index_file = os.path.join(static_dir, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"message": "Bienvenido a la API de Firma GOB. Visite /docs para Swagger UI."}
