import uuid
from datetime import datetime, timezone

from fastapi import Body, FastAPI

from app.routers.dte import router as dte_router
from app.routers.anulacion import router as anulacion_router
from app.routers.contingencia import router as contingencia_router

app = FastAPI(
    title="DTE Gateway SV",
    version="0.5.0",
    description="Gateway DTE El Salvador — Sprint 5"
)

# Routers v2 — FE/CCF/NC + Anulación + Contingencia
app.include_router(dte_router)
app.include_router(anulacion_router)
app.include_router(contingencia_router)


@app.get("/")
def root():
    return {"message": "DTE Gateway SV running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/dte/emit")
def emit_dte(payload: dict = Body(...)):
    """
    Endpoint legacy mock — mantenido por compatibilidad.
    Usar /v2/dte/emit para la integración real.
    """
    return {
        "status": "received",
        "uuid_dte": str(uuid.uuid4()),
        "received_at": datetime.now(timezone.utc).isoformat(),
        "mode": "mock",
        "echo": payload,
    }
