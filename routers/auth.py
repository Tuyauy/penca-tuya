import os
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, status, Depends, Request
from pydantic import BaseModel, EmailStr, validator
from typing import Optional
from database import get_supabase
from auth_utils import verify_password, get_password_hash, create_access_token

router = APIRouter()


class RegisterRequest(BaseModel):
    email: str
    username: str
    password: str
    full_name: Optional[str] = None

    @validator('email')
    def email_lower(cls, v):
        return v.lower().strip()

    @validator('username')
    def username_clean(cls, v):
        v = v.strip()
        if len(v) < 3:
            raise ValueError('El nombre de usuario debe tener al menos 3 caracteres')
        if len(v) > 30:
            raise ValueError('El nombre de usuario no puede tener mas de 30 caracteres')
        return v

    @validator('password')
    def password_strength(cls, v):
        if len(v) < 6:
            raise ValueError('La contrasena debe tener al menos 6 caracteres')
        return v


class LoginRequest(BaseModel):
    email: str
    password: str

    @validator('email')
    def email_lower(cls, v):
        return v.lower().strip()


class AuthResponse(BaseModel):
    token: str
    user: dict


@router.post("/register", response_model=AuthResponse)
async def register(req: RegisterRequest):
    sb = get_supabase()

    existing = sb.table("penca_users").select("id").eq("email", req.email).execute()
    if existing.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este email ya esta registrado"
        )

    existing_user = sb.table("penca_users").select("id").eq("username", req.username).execute()
    if existing_user.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este nombre de usuario ya esta en uso"
        )

    password_hash = get_password_hash(req.password)
    new_user = sb.table("penca_users").insert({
        "email": req.email,
        "username": req.username,
        "password_hash": password_hash,
        "full_name": req.full_name,
        "subscribed_newsletter": True,
        "total_points": 0,
        "prediction_points": 0,
        "purchase_points": 0
    }).execute()

    if not new_user.data:
        raise HTTPException(status_code=500, detail="Error al crear el usuario")

    user = new_user.data[0]
    token = create_access_token({
        "sub": str(user["id"]),
        "email": user["email"],
        "username": user["username"],
        "is_admin": user.get("is_admin", False)
    })

    return AuthResponse(
        token=token,
        user={
            "id": user["id"],
            "email": user["email"],
            "username": user["username"],
            "full_name": user["full_name"],
            "total_points": 0,
            "prediction_points": 0,
            "purchase_points": 0
        }
    )


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest):
    sb = get_supabase()
    result = sb.table("penca_users").select("*").eq("email", req.email).execute()

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contrasena incorrectos"
        )

    user = result.data[0]

    if not verify_password(req.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contrasena incorrectos"
        )

    token = create_access_token({
        "sub": str(user["id"]),
        "email": user["email"],
        "username": user["username"],
        "is_admin": user.get("is_admin", False)
    })

    return AuthResponse(
        token=token,
        user={
            "id": user["id"],
            "email": user["email"],
            "username": user["username"],
            "full_name": user["full_name"],
            "total_points": user["total_points"],
            "prediction_points": user["prediction_points"],
            "purchase_points": user["purchase_points"],
            "is_admin": user.get("is_admin", False)
        }
    )


@router.get("/profile")
async def profile(token_data: dict = Depends(__import__('auth_utils').get_current_user)):
    sb = get_supabase()
    result = sb.table("penca_users").select("*").eq("id", token_data["sub"]).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    user = result.data[0]
    user.pop("password_hash", None)
    return user


@router.post("/forgot-password")
async def forgot_password(request: Request):
    data = await request.json()
    email = data.get("email", "").strip().lower()

    sb = get_supabase()
    res = sb.table("penca_users").select("id, username").eq("email", email).execute()

    if not res.data:
        return {"message": "Si el email existe, recibiras un enlace."}

    user = res.data[0]
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()

    sb.table("password_reset_tokens").delete().eq("user_id", user["id"]).execute()

    sb.table("password_reset_tokens").insert({
        "token": token,
        "user_id": user["id"],
        "expires_at": expires_at
    }).execute()

    app_url = os.getenv("APP_URL", "https://penca-tuya-production.up.railway.app")
    reset_link = f"{app_url}/#reset-password?token={token}"

    try:
        import resend
        resend.api_key = os.getenv("RESEND_API_KEY")
        resend.Emails.send({
            "from": "Penca TUYA <noreply@tuyauy.com>",
            "to": [email],
            "subject": "Recuperar contrasena - Penca Tuya",
            "html": "<p>Hola " + user["username"] + "</p><p><a href='" + reset_link + "'>Resetear</a></p><p>Expira en 1 hora.</p>"
        })
    except Exception as e:
        print(f"Email error: {e}")
        raise


@router.post("/reset-password")
async def reset_password(request: Request):
    data = await request.json()
    token = data.get("token", "")
    new_password = data.get("new_password", "")

    if not token or not new_password:
        raise HTTPException(status_code=400, detail="Token y contrasena requeridos.")

    sb = get_supabase()

    res = sb.table("password_reset_tokens").select("*").eq("token", token).execute()

    if not res.data:
        raise HTTPException(status_code=400, detail="Token invalido o expirado.")

    token_data = res.data[0]
    expires_at = token_data["expires_at"]

    if isinstance(expires_at, str):
        try:
            expires_dt = datetime.fromisoformat(expires_at)
        except ValueError:
            expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    else:
        expires_dt = expires_at

    now = datetime.now(timezone.utc)
    if expires_dt.tzinfo is None:
        expires_dt = expires_dt.replace(tzinfo=timezone.utc)

    if now > expires_dt:
        sb.table("password_reset_tokens").delete().eq("token", token).execute()
        raise HTTPException(status_code=400, detail="Token expirado.")

    hashed = get_password_hash(new_password)
    sb.table("penca_users").update({"password_hash": hashed}).eq("id", token_data["user_id"]).execute()

    sb.table("password_reset_tokens").delete().eq("token", token).execute()

    return {"message": "Contrasena actualizada correctamente."}
