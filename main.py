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

from routers import auth, matches, predictions, ranking, admin, purchases, sportmonks
from database import get_supabase, reset_supabase

load_dotenv()

# ── APScheduler for auto-sync ─────────────────────────────────────────────────────────────
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler_enabled = True
except ImportError:
    _scheduler = None
    _scheduler_enabled = False

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


# ── Middleware de reconexión Supabase (Bug1 fix) ──────────────────────────────
@app.middleware("http")
async def supabase_reconnect_middleware(request: Request, call_next):
    """Resetea el cliente Supabase si hay un error de conexión Server disconnected."""
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        err_str = str(e)
        if "Server disconnected" in err_str or "RemoteProtocol" in err_str:
            reset_supabase()
        raise

# Routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(matches.router, prefix="/api/matches", tags=["matches"])
app.include_router(predictions.router, prefix="/api/predictions", tags=["predictions"])
app.include_router(ranking.router, prefix="/api/ranking", tags=["ranking"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(purchases.router, prefix="/api/purchases", tags=["purchases"])
app.include_router(sportmonks.router, prefix="/api", tags=["sportmonks"])

# ── Startup event: launch APScheduler ──────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    if _scheduler_enabled and _scheduler:
        from routers.sportmonks import sync_live_and_finished, _fix_stale_matches_without_sm_id
        from database import get_supabase as _get_sb

        # Sync live/finished every 2 min
        _scheduler.add_job(sync_live_and_finished, "interval", minutes=2, id="sm_sync", replace_existing=True)

        # Fallback: fix stale scheduled matches without sportmonks_id every 15 min
        def _run_fix_stale():
            try:
                sb = _get_sb()
                fixed = _fix_stale_matches_without_sm_id(sb)
                if fixed:
                    import logging
                    logging.getLogger(__name__).info("fix_stale: %d partidos marcados como pending_review", fixed)
            except Exception as _e:
                import logging
                logging.getLogger(__name__).error("fix_stale error: %s", _e)

        _scheduler.add_job(_run_fix_stale, "interval", minutes=15, id="fix_stale_sync", replace_existing=True)
        _scheduler.start()
# Servir JS y CSS sin cachÃ© para que los cambios se apliquen siempre
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

@app.get("/static/tuya-logo-v5.png")
async def serve_tuya_logo_v5():
    img_path = Path(__file__).parent / "static" / "tuya-logo-v5.png"
    content = img_path.read_bytes()
    return Response(
        content=content,
        media_type="image/png",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"}
    )

@app.get("/static/tuya-logo-v4.png")
async def serve_tuya_logo_v4():
    img_path = Path(__file__).parent / "static" / "tuya-logo-v4.png"
    content = img_path.read_bytes()
    return Response(
        content=content,
        media_type="image/png",
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

# Servir archivos estÃ¡ticos (imÃ¡genes, etc.)
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
