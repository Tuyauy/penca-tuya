"""
Router de predicciones
"""
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, validator
from typing import Optional
from database import get_supabase
from auth_utils import get_current_user
from datetime import datetime, timezone, timedelta

router = APIRouter()

KNOCKOUT_PHASES = {'r16', 'qf', 'sf', 'semi', 'third', 'final'}


class PredictionRequest(BaseModel):
    match_id: int
    predicted_home_score: int
    predicted_away_score: int
    # Solo para fases eliminatorias si hay empate
    predicted_extra_time: Optional[bool] = False
    predicted_penalties: Optional[bool] = False
    predicted_penalty_winner_id: Optional[int] = None
    predicted_et_winner_id: Optional[int] = None
    
    @validator('predicted_home_score', 'predicted_away_score')
    def score_non_negative(cls, v):
        if v < 0:
            raise ValueError('El marcador no puede ser negativo')
        if v > 30:
            raise ValueError('El marcador parece inválido')
        return v


@router.post("/")
async def submit_prediction(
    req: PredictionRequest,
    current_user: dict = Depends(get_current_user)
):
    """Enviar o actualizar una predicción"""
    sb = get_supabase()
    
    # Obtener el partido
    match_result = sb.table("matches").select("*").eq("id", req.match_id).execute()
    if not match_result.data:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    
    match = match_result.data[0]
    
    # Verificar que el partido no haya cerrado (30 min antes del inicio)
    match_date = match["match_date"]
    if isinstance(match_date, str):
        match_date = datetime.fromisoformat(match_date.replace("Z", "+00:00"))
    if match_date.tzinfo is None:
        match_date = match_date.replace(tzinfo=timezone.utc)
    cutoff = match_date - timedelta(minutes=30)
    now = datetime.now(timezone.utc)
    if now >= cutoff or match["predictions_locked"] or match["status"] in ["live", "finished"]:
        raise HTTPException(
            status_code=400,
            detail="Las predicciones para este partido ya están cerradas"
        )
    
    is_knockout = match["phase"] in KNOCKOUT_PHASES
    
    # Validaciones para fase eliminatoria
    if is_knockout:
        predicted_draw = req.predicted_home_score == req.predicted_away_score
        if predicted_draw:
            if not req.predicted_extra_time and not req.predicted_penalties:
                # Si predicen empate en eliminatorias, DEBEN indicar cómo se resuelve
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="En fases eliminatorias, si predices empate debes indicar si gana por tiempo extra o penales"
                )
            if req.predicted_penalties and not req.predicted_penalty_winner_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Debes indicar qué equipo gana en los penales"
                )
            if req.predicted_extra_time and not req.predicted_penalties and not req.predicted_et_winner_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Debes indicar qué equipo gana en el tiempo extra"
                )
    
    # Verificar si ya existe una predicción
    existing = sb.table("predictions").select("id").eq(
        "user_id", current_user["sub"]
    ).eq("match_id", req.match_id).execute()
    
    prediction_data = {
        "user_id": current_user["sub"],
        "match_id": req.match_id,
        "predicted_home_score": req.predicted_home_score,
        "predicted_away_score": req.predicted_away_score,
        "predicted_extra_time": req.predicted_extra_time if is_knockout else False,
        "predicted_penalties": req.predicted_penalties if is_knockout else False,
        "predicted_penalty_winner_id": req.predicted_penalty_winner_id if is_knockout else None,
        "predicted_et_winner_id": req.predicted_et_winner_id if is_knockout else None,
        "points_calculated": False,
        "points_earned": None
    }
    
    if existing.data:
        # Actualizar predicción existente
        result = sb.table("predictions").update(prediction_data).eq(
            "id", existing.data[0]["id"]
        ).execute()
    else:
        # Crear nueva predicción
        result = sb.table("predictions").insert(prediction_data).execute()
    
    if not result.data:
        raise HTTPException(status_code=500, detail="Error al guardar la predicción")
    
    return {"message": "Predicción guardada correctamente", "prediction": result.data[0]}


@router.get("/my")
async def get_my_predictions(current_user: dict = Depends(get_current_user)):
    """Obtener todas las predicciones del usuario actual"""
    sb = get_supabase()
    
    result = sb.table("predictions").select("""
        *,
        matches!match_id(
            *,
            home_team:teams!matches_home_team_id_fkey(id, name, code, flag_url),
            away_team:teams!matches_away_team_id_fkey(id, name, code, flag_url)
        )
    """).eq("user_id", current_user["sub"]).order("created_at", desc=True).execute()
    
    return result.data or []


@router.get("/match/{match_id}")
async def get_match_predictions(
    match_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Obtener la predicción del usuario para un partido específico"""
    sb = get_supabase()
    
    result = sb.table("predictions").select("*").eq(
        "user_id", current_user["sub"]
    ).eq("match_id", match_id).execute()
    
    if not result.data:
        return None
    
    return result.data[0]


@router.get("/stats")
async def get_my_stats(current_user: dict = Depends(get_current_user)):
    """Estadísticas del usuario"""
    sb = get_supabase()
    
    user = sb.table("penca_users").select("*").eq(
        "id", current_user["sub"]
    ).execute()
    
    if not user.data:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    preds = sb.table("predictions").select("*").eq(
        "user_id", current_user["sub"]
    ).eq("points_calculated", True).execute()
    
    preds_data = preds.data or []
    
    stats = {
        "total_predictions": len(preds_data),
        "exact_results": len([p for p in preds_data if p["points_earned"] == 10]),
        "exact_draws": len([p for p in preds_data if p["points_earned"] == 7]),
        "exact_differences": len([p for p in preds_data if p["points_earned"] == 5]),
        "correct_winners": len([p for p in preds_data if p["points_earned"] == 3]),
        "misses": len([p for p in preds_data if p["points_earned"] == 0]),
        "prediction_points": user.data[0]["prediction_points"],
        "purchase_points": user.data[0]["purchase_points"],
        "total_points": user.data[0]["total_points"]
    }
    
    return stats


@router.get("/users/{username}/predictions")
async def get_rival_predictions(username: str):
    """Predicciones publicas de un usuario (solo partidos ya no editables)"""
    sb = get_supabase()

    # Buscar el usuario por username
    user_res = sb.table("penca_users").select("id, username, total_points").eq("username", username).single().execute()
    if not user_res.data:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    user_data = user_res.data

    # Calcular el corte: now - 30 minutos en UTC
    cutoff = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()

    # Traer predicciones del usuario (sin join embebido)
    preds_res = sb.table("predictions").select(
        "match_id, predicted_home_score, predicted_away_score, predicted_extra_time, predicted_penalties, points_earned"
    ).eq("user_id", user_data["id"]).execute()

    if not preds_res.data:
        return {"user": user_data, "predictions": []}

    # Obtener matches por separado
    match_ids = [p["match_id"] for p in preds_res.data if p.get("match_id")]
    matches_res = sb.table("matches").select(
        "id, match_date, phase, status, home_score, away_score, home_team:teams!matches_home_team_id_fkey(id, name, code, flag_url), away_team:teams!matches_away_team_id_fkey(id, name, code, flag_url)"
    ).in_("id", match_ids).execute()
    matches_by_id = {m["id"]: m for m in (matches_res.data or [])}

    # Filtrar partidos ya no editables: status='finished' O match_date <= cutoff
    cutoff_dt = datetime.fromisoformat(cutoff)
    visible = []
    for p in preds_res.data:
        mid = p.get("match_id")
        m = matches_by_id.get(mid)
        if not m:
            continue
        match_status = m.get("status", "")
        match_date_str = m.get("match_date", "")
        try:
            match_dt = datetime.fromisoformat(match_date_str.replace("Z", "+00:00"))
            if match_status != "scheduled" or match_dt <= cutoff_dt:
                p["matches"] = m
                visible.append(p)
        except Exception:
            pass

    # Ordenar por fecha del partido ascendente
    visible.sort(key=lambda p: p["matches"]["match_date"])

    return {"user": user_data, "predictions": visible}
