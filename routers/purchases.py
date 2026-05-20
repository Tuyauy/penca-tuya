"""
Router de puntos por compras en TUYA
"""
from fastapi import APIRouter, HTTPException, Depends, status, Request
from pydantic import BaseModel
from typing import Optional
import os
from database import get_supabase
from auth_utils import require_admin

router = APIRouter()

# Puntos por compra = equivalente a resultado exacto (10 pts)
PURCHASE_POINTS = 10


class PurchaseGrantRequest(BaseModel):
    email: str  # email de la compra (debe coincidir con usuario de penca)
    order_id: Optional[str] = None
    order_amount: Optional[float] = None
    description: Optional[str] = "Compra en TUYA"


class WebhookPurchaseRequest(BaseModel):
    """Estructura esperada del webhook de Luna Growth"""
    email: str
    order_id: str
    order_amount: Optional[float] = None
    customer_name: Optional[str] = None


@router.post("/grant")
async def grant_purchase_points(
    req: PurchaseGrantRequest,
    admin: dict = Depends(require_admin)
):
    """
    Admin: Otorgar puntos por compra manualmente.
    El email debe coincidir con un usuario registrado en la penca.
    """
    sb = get_supabase()
    
    email = req.email.lower().strip()
    
    # Buscar usuario por email
    user_result = sb.table("penca_users").select("id, username, email, total_points").eq(
        "email", email
    ).execute()
    
    if not user_result.data:
        raise HTTPException(
            status_code=404,
            detail=f"No existe ningún participante registrado con el email: {email}"
        )
    
    user = user_result.data[0]
    
    # Verificar si ya se procesó esta orden
    if req.order_id:
        existing = sb.table("purchase_points").select("id").eq(
            "order_id", req.order_id
        ).execute()
        if existing.data:
            raise HTTPException(
                status_code=400,
                detail=f"La orden {req.order_id} ya fue procesada"
            )
    
    # Registrar puntos
    pp_result = sb.table("purchase_points").insert({
        "user_id": user["id"],
        "email": email,
        "order_id": req.order_id,
        "order_amount": req.order_amount,
        "points_granted": PURCHASE_POINTS,
        "description": req.description or "Compra en TUYA",
        "granted_by": "admin"
    }).execute()
    
    if not pp_result.data:
        raise HTTPException(status_code=500, detail="Error al registrar los puntos")
    
    # Actualizar totales del usuario
    sb.rpc("update_user_purchase_points", {"user_id_param": user["id"]}).execute()
    
    # Obtener puntos actualizados
    updated_user = sb.table("penca_users").select("total_points, purchase_points").eq(
        "id", user["id"]
    ).execute()
    
    return {
        "message": f"Se otorgaron {PURCHASE_POINTS} puntos a {user['username']} por su compra en TUYA",
        "user": user["username"],
        "email": email,
        "points_granted": PURCHASE_POINTS,
        "new_total": updated_user.data[0]["total_points"] if updated_user.data else None
    }


@router.post("/webhook/luna-growth")
async def webhook_luna_growth(
    request: Request
):
    """
    Webhook para recibir notificaciones de compra desde Luna Growth.
    Requiere configurar el header X-Webhook-Secret en Luna Growth
    y setear WEBHOOK_SECRET en las variables de entorno.
    """
    # Verificar el secret
    webhook_secret = os.getenv("WEBHOOK_SECRET")
    if webhook_secret:
        provided_secret = request.headers.get("X-Webhook-Secret") or \
                         request.headers.get("X-Luna-Secret")
        if provided_secret != webhook_secret:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Webhook secret inválido"
            )
    
    body = await request.json()
    
    # Intentar extraer email y order_id de diferentes formatos de webhook
    email = (
        body.get("email") or 
        body.get("customer_email") or 
        body.get("billing_email") or
        (body.get("customer") or {}).get("email")
    )
    
    order_id = (
        body.get("order_id") or 
        body.get("id") or 
        body.get("order_number") or
        str(body.get("number", ""))
    )
    
    order_amount = body.get("total") or body.get("order_amount") or body.get("amount")
    
    if not email:
        return {"status": "ignored", "reason": "No email found in webhook payload"}
    
    email = email.lower().strip()
    sb = get_supabase()
    
    # Buscar usuario
    user_result = sb.table("penca_users").select("id, username").eq("email", email).execute()
    
    if not user_result.data:
        # El cliente no está registrado en la penca — no pasa nada
        return {
            "status": "skipped",
            "reason": f"Email {email} not registered in penca"
        }
    
    user = user_result.data[0]
    
    # Verificar si ya fue procesada
    if order_id:
        existing = sb.table("purchase_points").select("id").eq("order_id", order_id).execute()
        if existing.data:
            return {"status": "duplicate", "reason": f"Order {order_id} already processed"}
    
    # Registrar puntos
    sb.table("purchase_points").insert({
        "user_id": user["id"],
        "email": email,
        "order_id": order_id,
        "order_amount": float(order_amount) if order_amount else None,
        "points_granted": PURCHASE_POINTS,
        "description": f"Compra en TUYA #{order_id}",
        "granted_by": "webhook"
    }).execute()
    
    # Actualizar totales
    sb.rpc("update_user_purchase_points", {"user_id_param": user["id"]}).execute()
    
    return {
        "status": "ok",
        "message": f"Puntos otorgados a {user['username']}",
        "points_granted": PURCHASE_POINTS
    }


@router.get("/history/{user_id}")
async def get_purchase_history(
    user_id: str,
    admin: dict = Depends(require_admin)
):
    """Historial de puntos por compra de un usuario"""
    sb = get_supabase()
    result = sb.table("purchase_points").select("*").eq(
        "user_id", user_id
    ).order("created_at", desc=True).execute()
    return result.data or []
