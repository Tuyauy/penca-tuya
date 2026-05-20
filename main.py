"""
Penca TUYA Mundial 2026 - Backend FastAPI
"""
from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv
from pathlib import Path

from routers import auth, matches, predictions, ranking, admin, purchases
from database import get_supabase

load_dotenv()

app = FastAPI(
    title="Penca TUYA Mundial 2026",
    description="API para la penca mundialista de TUYA",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(matches.router, prefix="/api/matches", tags=["matches"])
app.include_router(predictions.router, prefix="/api/predictions", tags=["predictions"])
app.include_router(ranking.router, prefix="/api/ranking", tags=["ranking"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(purchases.router, prefix="/api/purchases", tags=["purchases"])

# Servir archivos estáticos
static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Servir el frontend (SPA)
@app.get("/", response_class=HTMLResponse)
async def root():
    html_path = Path(__file__).parent / "static" / "index.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(), status_code=200)
    return HTMLResponse(content="<h1>Penca TUYA - Iniciando...</h1>", status_code=200)

@app.get("/{full_path:path}", response_class=HTMLResponse)
async def catch_all(full_path: str):
    # No interceptar rutas de API
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404)
    html_path = Path(__file__).parent / "static" / "index.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(), status_code=200)
    return HTMLResponse(content="<h1>Not Found</h1>", status_code=404)

@app.get("/api/health")
async def health():
    return {"status": "ok", "app": "Penca TUYA Mundial 2026"}
