from fastapi import FastAPI

from app.api import health

app = FastAPI(title="Shop API", version="0.1.0")

app.include_router(health.router, prefix="/api/v1")


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Shop API is running", "docs": "/docs"}