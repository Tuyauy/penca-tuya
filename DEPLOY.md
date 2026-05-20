# 🚀 Guía de Deploy — Penca TUYA Mundial 2026

Tiempo estimado: **30-45 minutos**
Costo: **$0/mes** (tiers gratuitos)

---

## PASO 1 — Crear base de datos en Supabase (10 min)

1. Ir a **https://supabase.com** → "Start your project" → Crear cuenta
2. "New project" → Nombre: `penca-tuya` → Elegir región: **South America (São Paulo)**
3. Guardar la **contraseña de base de datos** en un lugar seguro
4. Esperar que el proyecto cargue (~2 min)

### Cargar el schema:
5. Ir a **SQL Editor** (icono de código en el menú izquierdo)
6. Pegar el contenido de `supabase_schema.sql` y ejecutar ▶️
7. Pegar el contenido de `fixture_data.sql` y ejecutar ▶️

### Obtener las claves:
8. Ir a **Settings → API**
9. Copiar:
   - `Project URL` → es tu `SUPABASE_URL`
   - `anon public` → es tu `SUPABASE_KEY`
   - `service_role secret` → es tu `SUPABASE_SERVICE_KEY` ⚠️ no compartir

---

## PASO 2 — Crear cuenta en Railway (10 min)

1. Ir a **https://railway.app** → "Login with GitHub"
2. "New Project" → "Deploy from GitHub repo"
3. Subir el código a GitHub primero (ver abajo) o usar "Deploy from template"

### Subir a GitHub:
```bash
cd penca-tuya
git init
git add .
git commit -m "Penca TUYA Mundial 2026"
# Crear repo en github.com y seguir instrucciones
git remote add origin https://github.com/TU_USUARIO/penca-tuya.git
git push -u origin main
```

### En Railway:
4. Seleccionar el repo `penca-tuya`
5. Railway detecta automáticamente que es Python

---

## PASO 3 — Variables de entorno en Railway

En Railway → tu proyecto → **Variables**, agregar:

| Variable | Valor |
|----------|-------|
| `SUPABASE_URL` | tu URL de Supabase |
| `SUPABASE_KEY` | tu anon key |
| `SUPABASE_SERVICE_KEY` | tu service role key |
| `JWT_SECRET` | una clave larga aleatoria (ej: `tuya-penca-2026-secreto-super-largo`) |
| `WEBHOOK_SECRET` | otra clave para el webhook de Luna Growth (opcional) |
| `PORT` | `8000` |

---

## PASO 4 — Archivo de inicio

Railway necesita saber cómo arrancar la app. Crear `Procfile` en la raíz:
```
web: uvicorn main:app --host 0.0.0.0 --port $PORT
```

O `railway.toml`:
```toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "uvicorn main:app --host 0.0.0.0 --port $PORT"
```

---

## PASO 5 — Deploy

1. En Railway → "Deploy" → esperar ~3 min
2. Ir a **Settings → Networking → Generate Domain**
3. Tu URL será algo como: `https://penca-tuya-production.up.railway.app`

---

## PASO 6 — Crear usuario admin

1. Registrarte en la penca con tu email
2. En Supabase → **Table Editor → penca_users**
3. Encontrar tu usuario y editar `is_admin = true`

Eso te da acceso al panel admin para:
- Cargar resultados de partidos
- Otorgar puntos por compras
- Ver estadísticas

---

## PASO 7 — Dominio personalizado (opcional)

Si querés `penca.tuyauy.com`:

1. En Railway → Settings → Custom Domain → agregar `penca.tuyauy.com`
2. Railway te da un CNAME → agregar en tu proveedor de DNS
3. Listo en ~10 min

Si no tenés acceso al DNS de tuyauy.com, podés usar:
- `pencatuya.com` (dominio nuevo ~$15/año en NIC.uy o GoDaddy)
- O simplemente la URL de Railway que es gratuita

---

## PASO 8 — Webhook con Luna Growth (para puntos por compra automáticos)

Si Luna Growth soporta webhooks:

1. En Luna Growth → Configuración → Webhooks → Agregar URL:
   `https://tu-url.railway.app/api/purchases/webhook/luna-growth`
2. Evento: `order.paid` o `order.completed`
3. Secret: el mismo valor que pusiste en `WEBHOOK_SECRET`

Si Luna Growth no soporta webhooks, usás el **panel admin** para registrar compras manualmente (es rápido, solo necesitás el email del cliente).

---

## Mantenimiento durante el mundial

### Cada día que hay partidos:
1. Antes del partido → bloquear predicciones (panel admin → ID del partido → Bloquear)
2. Después del partido → cargar resultado (panel admin → ID → Resultado)
3. Los puntos se calculan automáticamente 🎉

### Cada vez que alguien compra en TUYA:
1. Panel admin → Puntos por Compra → Email del cliente → Otorgar
2. O configurar el webhook para que sea automático

---

## Estructura del proyecto

```
penca-tuya/
├── main.py              # App principal FastAPI
├── database.py          # Conexión Supabase
├── auth_utils.py        # JWT y autenticación
├── requirements.txt     # Dependencias Python
├── routers/
│   ├── auth.py          # Registro y login
│   ├── matches.py       # Fixture y partidos
│   ├── predictions.py   # Pronósticos
│   ├── ranking.py       # Tabla de posiciones
│   ├── admin.py         # Panel de administración
│   └── purchases.py     # Puntos por compras
├── static/
│   ├── index.html       # Frontend SPA
│   ├── css/styles.css   # Estilos TUYA
│   └── js/app.js        # Lógica frontend
└── supabase_schema.sql  # Schema de base de datos
```

---

## Soporte

Ante cualquier duda, el panel admin está en: `tu-url/` → iniciar sesión con tu cuenta admin → botón "Admin" en el navbar.
