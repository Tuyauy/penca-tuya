"""
Router de predicciones
"""
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, validator
from typing import Optional
from database import get_supabase
from auth_utils import get_current_user

router = APIRouter()

KNOCKOUT_PHASES = {'r16', 'qf', 'sf', 'third', 'final'}


class PredictionRequest(BaseModel):
    match_id: int
    predicted_home_score: int
    predicted_away_score: int
    # Solo para fases eliminatorias si hay empate
    predicted_extra_time: Optional[bool] = False
    predicted_penalties: Optional[bool] = False
    predicted_penalty_winner_id: Optional[int] = None
    
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
    
    # Verificar que el partido no haya empezado
    if match["predictions_locked"] or match["status"] in ["live", "finished"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
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
        match:matches(
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
