import uuid
from datetime import datetime, timezone

from fastapi import Body, FastAPI

app = FastAPI(
    title="DTE Gateway SV",
    version="0.1.0",
    description="Gateway base para integración DTE El Salvador"
)

@app.get("/")
def root():
    return {"message": "DTE Gateway SV running"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/dte/emit")
def emit_dte(payload: dict = Body(...)):
    """
    Endpoint mock de emisión DTE.
    Acepta cualquier payload JSON y devuelve un UUID simulado.
    mode=mock indica que no hay envío real al Ministerio de Hacienda.
    """
    return {
        "status": "received",
        "uuid_dte": str(uuid.uuid4()),
        "received_at": datetime.now(timezone.utc).isoformat(),
        "mode": "mock",
        "echo": payload,
    }
