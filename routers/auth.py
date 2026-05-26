"""
Router de autenticación
"""
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
            raise ValueError('El nombre de usuario no puede tener más de 30 caracteres')
        return v
    
    @validator('password')
    def password_strength(cls, v):
        if len(v) < 6:
            raise ValueError('La contraseña debe tener al menos 6 caracteres')
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
    
    # Verificar si el email ya existe
    existing = sb.table("penca_users").select("id").eq("email", req.email).execute()
    if existing.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este email ya está registrado"
        )
    
    # Verificar si el username ya existe
    existing_user = sb.table("penca_users").select("id").eq("username", req.username).execute()
    if existing_user.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este nombre de usuario ya está en uso"
        )
    
    # Crear usuario
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
            detail="Email o contraseña incorrectos"
        )
    
    user = result.data[0]
    
    if not verify_password(req.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos"
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


@router.get("/me")
async def get_me(current_user: dict = Depends(lambda: None)):
    """Obtener perfil del usuario actual"""
    from auth_utils import get_current_user
    from fastapi import Depends
    # handled in route decorator
    pass


@router.get("/profile")
async def profile(token_data: dict = Depends(__import__('auth_utils').get_current_user)):
    sb = get_supabase()
    result = sb.table("penca_users").select("*").eq("id", token_data["sub"]).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    user = result.data[0]
    user.pop("password_hash", None)
    return user


import secrets
from datetime import datetime, timedelta

_reset_tokens = {}

@router.post("/forgot-password")
async def forgot_password(request: Request):
    data = await request.json()
    email = data.get("email", "").strip().lower()
    sb = get_supabase()
    res = sb.table("users").select("id, username").eq("email", email).execute()
    if not res.data:
        return {"message": "Si el email existe, recibirás un enlace."}
    token = secrets.token_urlsafe(32)
    user = res.data[0]
    _reset_tokens[token] = {"user_id": user["id"], "expires": datetime.utcnow() + timedelta(hours=1)}
    app_url = os.getenv("APP_URL", "https://penca-tuya-production.up.railway.app")
    reset_link = f"{app_url}/reset-password?token={token}"
    try:
        resend_key = os.getenv("RESEND_API_KEY")
        if resend_key:
            import resend
            resend.api_key = resend_key
            resend.Emails.send({"from": os.getenv("RESEND_FROM_EMAIL"), "to": email, "subject": "Recuperar contraseña - Penca Tuya", "html": f"<p>Hola {user.username},</p><p><a href=\'{reset_link}\'>Resetear contraseña</a></p><p>Expira en 1 hora.</p>"})
    except Exception as e:
        print(f"Email error: {e}")
    return {"message": "Si el email existe, recibirás un enlace."}

@router.post("/reset-password")
async def reset_password(request: Request):
    data = await request.json()
    token = data.get("token", "")
    new_password = data.get("password", "")
    if not token or not new_password:
        raise HTTPException(status_code=400, detail="Token y contraseña requeridos.")
    token_data = _reset_tokens.get(token)
    if not token_data:
        raise HTTPException(status_code=400, detail="Token inválido o expirado.")
    if datetime.utcnow() > token_data["expires"]:
        del _reset_tokens[token]
        raise HTTPException(status_code=400, detail="Token expirado.")
    sb = get_supabase()
    hashed = get_password_hash(new_password)
    sb.table("users").update({"hashed_password": hashed}).eq("id", token_data["user_id"]).execute()
    del _reset_tokens[token]
    return {"message": "Contraseña actualizada correctamente."}
