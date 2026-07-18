from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.domain.entities import User
from app.persistence.repositories.user_repository import UserRepository
from app.schemas.user import (
    PlanningProfileResponse,
    PlanningProfileUpdateRequest,
    UserResponse,
    UserUpdateRequest,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user, from_attributes=True)


@router.patch("/me", response_model=UserResponse)
async def update_me(
    body: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    updated = await UserRepository(db).update(
        current_user.id,
        full_name=body.full_name,
        base_currency=body.base_currency,
        date_of_birth=body.date_of_birth,
    )
    await db.commit()
    return UserResponse.model_validate(updated, from_attributes=True)


@router.get("/me/planning-profile", response_model=PlanningProfileResponse)
async def get_planning_profile(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> PlanningProfileResponse:
    profile = await UserRepository(db).get_planning_profile(current_user.id)
    return PlanningProfileResponse.model_validate(profile, from_attributes=True)


@router.patch("/me/planning-profile", response_model=PlanningProfileResponse)
async def update_planning_profile(
    body: PlanningProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlanningProfileResponse:
    updated = await UserRepository(db).update_planning_profile(
        current_user.id, **body.model_dump(exclude_unset=True)
    )
    await db.commit()
    return PlanningProfileResponse.model_validate(updated, from_attributes=True)
