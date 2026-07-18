from fastapi import APIRouter

from app.api.v1.routes import (
    accounts,
    agent,
    auth,
    financial_health,
    goals,
    insights,
    recommendations,
    scenarios,
    simulations,
    transactions,
    users,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(accounts.router)
api_router.include_router(transactions.router)
api_router.include_router(goals.router)
api_router.include_router(scenarios.router)
api_router.include_router(simulations.router)
api_router.include_router(recommendations.router)
api_router.include_router(insights.router)
api_router.include_router(financial_health.router)
api_router.include_router(agent.router)
