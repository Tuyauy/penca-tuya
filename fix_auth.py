import re

path = "/Users/guillermodeal/penca-tuya/routers/auth.py"
with open(path) as f:
    content = f.read()

# Fix forgot_password: reemplazar db.query por supabase
content = content.replace(
    "async def forgot_password(request: Request, db = Depends(get_supabase)):",
    "async def forgot_password(request: Request):"
)
content = content.replace(
    "    user = db.query(User).filter(User.email == email).first()\n    if not user:",
    "    sb = get_supabase()\n    res = sb.table(\"users\").select(\"id, username\").eq(\"email\", email).execute()\n    if not res.data:"
)
content = content.replace(
    '    _reset_tokens[token] = {"user_id": user.id,',
    '    user = res.data[0]\n    _reset_tokens[token] = {"user_id": user["id"],'
)
content = content.replace(
    '                "html": f"<p>Hola {user.username},',
    '                "html": f"<p>Hola {user[\'username\']},'
)

# Fix reset_password
content = content.replace(
    "async def reset_password(request: Request, db = Depends(get_supabase)):",
    "async def reset_password(request: Request):"
)
content = content.replace(
    "    user = db.query(User).filter(User.id == token_data[\"user_id\"]).first()\n    if not user:\n        raise HTTPException(status_code=404, detail=\"Usuario no encontrado.\")\n    user.hashed_password = pwd_context.hash(new_password)\n    db.commit()",
    "    sb = get_supabase()\n    hashed = get_password_hash(new_password)\n    sb.table(\"users\").update({\"hashed_password\": hashed}).eq(\"id\", token_data[\"user_id\"]).execute()"
)

with open(path, "w") as f:
    f.write(content)
print("OK")
