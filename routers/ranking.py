"""
Router de ranking
"""
from fastapi import APIRouter, Depends
from typing import Optional
from database import get_supabase
from auth_utils import get_current_user_optional

router = APIRouter()


@router.get("/")
async def get_ranking(
    limit: int = 500,
    offset: int = 0,
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """Obtener el ranking general"""
    sb = get_supabase()

    # Traer todos los usuarios para asignar posicion consecutiva correcta
    all_result = sb.table("ranking").select("*").execute()
    all_users = all_result.data or []

    # Ordenar por total_points DESC, luego username ASC como desempate
    all_users.sort(key=lambda u: (-u.get("total_points", 0), u.get("username", "").lower()))

    # Asignar posicion consecutiva unica (row_number)
    for i, user in enumerate(all_users):
        user["position"] = i + 1

    # Paginar
    ranking = all_users[offset: offset + limit]
    total = len(all_users)

    # Si hay usuario logueado, buscar su posicion
    user_position = None
    if current_user:
        for user in all_users:
            if user.get("id") == current_user["sub"]:
                user_position = user
                break

    return {
        "ranking": ranking,
        "total": total,
        "user_position": user_position
    }


@router.get("/top3")
async def get_top3():
    """Obtener el top 3 para mostrar en la landing"""
    sb = get_supabase()

    # Traer todos y calcular posicion correcta
    all_result = sb.table("ranking").select("*").execute()
    all_users = all_result.data or []

    # Ordenar por total_points DESC, luego username ASC
    all_users.sort(key=lambda u: (-u.get("total_points", 0), u.get("username", "").lower()))

    # Asignar posicion consecutiva
    for i, user in enumerate(all_users):
        user["position"] = i + 1

    return all_users[:3]


@router.get("/stats")
async def get_global_stats():
    """Estadisticas globales de la penca"""
    sb = get_supabase()

    users_count = sb.table("penca_users").select("id", count="exact").execute()
    preds_count = sb.table("predictions").select("id", count="exact").execute()
    finished_matches = sb.table("matches").select("id", count="exact").eq(
        "status", "finished"
    ).execute()

    return {
        "total_participants": users_count.count or 0,
        "total_predictions": preds_count.count or 0,
        "matches_played": finished_matches.count or 0
    }
