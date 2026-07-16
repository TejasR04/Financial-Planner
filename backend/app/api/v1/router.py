from fastapi import APIRouter

from app.api.v1.routes import accounts, agent, auth, simulations, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(accounts.router)
api_router.include_router(simulations.router)
api_router.include_router(agent.router)
