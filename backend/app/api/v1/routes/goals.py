from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.domain.entities import Goal, User
from app.domain.enums import GoalStatus
from app.persistence.repositories.goal_repository import GoalRepository
from app.schemas.goal import GoalCreateRequest, GoalResponse, GoalUpdateRequest

router = APIRouter(prefix="/goals", tags=["goals"])


@router.get("", response_model=list[GoalResponse])
async def list_goals(
    current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[GoalResponse]:
    goals = await GoalRepository(db).list_for_user(current_user.id)
    return [GoalResponse.model_validate(g, from_attributes=True) for g in goals]


@router.post("", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
async def create_goal(
    body: GoalCreateRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> GoalResponse:
    goal = Goal(
        id=uuid4(),
        user_id=current_user.id,
        title=body.title,
        target_amount=body.target_amount,
        target_date=body.target_date,
        target_age=body.target_age,
        priority=body.priority,
        status=GoalStatus.UPCOMING,
        linked_account_id=body.linked_account_id,
    )
    created = await GoalRepository(db).create(current_user.id, goal)
    await db.commit()
    return GoalResponse.model_validate(created, from_attributes=True)


@router.patch("/{goal_id}", response_model=GoalResponse)
async def update_goal(
    goal_id: UUID,
    body: GoalUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GoalResponse:
    updated = await GoalRepository(db).update(goal_id, **body.model_dump(exclude_unset=True))
    await db.commit()
    return GoalResponse.model_validate(updated, from_attributes=True)


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_goal(
    goal_id: UUID, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> None:
    await GoalRepository(db).delete(goal_id)
    await db.commit()
