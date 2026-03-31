from fastapi import FastAPI

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
