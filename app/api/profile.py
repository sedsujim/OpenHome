from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user
from app.models.schemas import PlanLimitsResponse, ProfileResponse
from app.plans import get_plan_limits, normalize_plan_id
from app.services.auth import SupabaseService, get_supabase

router = APIRouter()


@router.get("/", response_model=ProfileResponse)
async def get_profile(
    user: dict = Depends(get_current_user),
    auth: SupabaseService = Depends(get_supabase),
):
    if user.get("id") == "anonymous":
        raise HTTPException(401, "Authentication required")

    profile = await auth.ensure_profile(user["id"])
    plan_id = normalize_plan_id(profile.get("plan"))

    return ProfileResponse(
        id=user["id"],
        email=user.get("email", ""),
        username=profile.get("username"),
        plan=plan_id,
        limits=PlanLimitsResponse(**get_plan_limits(plan_id)),
    )
