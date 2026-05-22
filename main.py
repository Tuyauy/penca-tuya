"""
Penca TUYA Mundial 2026 - Backend FastAPI
"""
from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
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

# Servir JS y CSS sin caché para que los cambios se apliquen siempre
@app.get("/static/js/app.js")
async def serve_js():
    js_path = Path(__file__).parent / "static" / "js" / "app.js"
    content = js_path.read_bytes()
    return Response(
        content=content,
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"}
    )

@app.get("/static/css/styles.css")
async def serve_css():
    css_path = Path(__file__).parent / "static" / "css" / "styles.css"
    content = css_path.read_bytes()
    return Response(
        content=content,
        media_type="text/css",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"}
    )

@app.get("/static/logo-penca-hero-src.jpg")
async def serve_hero_src():
    img_path = Path(__file__).parent / "static" / "logo-penca-hero-src.jpg"
    content = img_path.read_bytes()
    return Response(
        content=content,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"}
    )

@app.get("/static/tuya-logo-v3.png")
async def serve_tuya_logo_v3():
    img_path = Path(__file__).parent / "static" / "tuya-logo-v3.png"
    content = img_path.read_bytes()
    return Response(
        content=content,
        media_type="image/png",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"}
    )

@app.get("/static/tuya-logo-v2.png")
async def serve_tuya_logo_v2():
    img_path = Path(__file__).parent / "static" / "tuya-logo-v2.png"
    content = img_path.read_bytes()
    return Response(
        content=content,
        media_type="image/png",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"}
    )

@app.get("/static/logo-penca-hero.png")
async def serve_hero_png():
    img_path = Path(__file__).parent / "static" / "logo-penca-hero.png"
    content = img_path.read_bytes()
    return Response(
        content=content,
        media_type="image/png",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"}
    )

@app.get("/static/logo-penca-hero.jpg")
async def serve_hero_img():
    img_path = Path(__file__).parent / "static" / "logo-penca-hero.jpg"
    content = img_path.read_bytes()
    return Response(
        content=content,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"}
    )

@app.get("/static/logo-tuya-clean.png")
async def serve_logo_clean():
    img_path = Path(__file__).parent / "static" / "logo-tuya-clean.png"
    content = img_path.read_bytes()
    return Response(
        content=content,
        media_type="image/png",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
    )

@app.get("/static/logo-tuya-full.jpg")
async def serve_logo_full():
    img_path = Path(__file__).parent / "static" / "logo-tuya-full.jpg"
    content = img_path.read_bytes()
    return Response(
        content=content,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
    )

# Servir archivos estáticos (imágenes, etc.)
static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Servir el frontend (SPA)
@app.get("/", response_class=HTMLResponse)
async def root():
    html_path = Path(__file__).parent / "static" / "index.html"
    if html_path.exists():
        return HTMLResponse(
            content=html_path.read_text(),
            status_code=200,
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )
    return HTMLResponse(content="<h1>Penca TUYA - Iniciando...</h1>", status_code=200)

@app.get("/{full_path:path}", response_class=HTMLResponse)
async def catch_all(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404)
    html_path = Path(__file__).parent / "static" / "index.html"
    if html_path.exists():
        return HTMLResponse(
            content=html_path.read_text(),
            status_code=200,
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )
    return HTMLResponse(content="<h1>Not Found</h1>", status_code=404)

@app.get("/api/health")
async def health():
    return {"status": "ok", "app": "Penca TUYA Mundial 2026"}
