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
    
    result = sb.table("ranking").select("*").range(offset, offset + limit - 1).execute()
    ranking = result.data or []
    
    # Contar total
    total_result = sb.table("penca_users").select("id", count="exact").execute()
    total = total_result.count or len(ranking)
    
    # Si hay usuario logueado, buscar su posición
    user_position = None
    if current_user:
        user_rank = sb.table("ranking").select("*").eq(
            "id", current_user["sub"]
        ).execute()
        if user_rank.data:
            user_position = user_rank.data[0]
    
    return {
        "ranking": ranking,
        "total": total,
        "user_position": user_position
    }


@router.get("/top3")
async def get_top3():
    """Obtener el top 3 para mostrar en la landing"""
    sb = get_supabase()
    result = sb.table("ranking").select("*").limit(3).execute()
    return result.data or []


@router.get("/stats")
async def get_global_stats():
    """Estadísticas globales de la penca"""
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
