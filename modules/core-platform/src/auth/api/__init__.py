"""API aggregator — includes all auth sub-routers under /api/v1.

The application composition layer imports ``auth_api_router`` from
``src.auth`` and mounts it at ``/api/v1``.
"""

from fastapi import APIRouter

from src.auth.api.auth_router import router as _auth_router
from src.auth.api.role_router import router as _role_router
from src.auth.api.user_router import router as _user_router

auth_api_router = APIRouter(prefix="/api/v1")
auth_api_router.include_router(_auth_router)
auth_api_router.include_router(_user_router)
auth_api_router.include_router(_role_router)

__all__ = ["auth_api_router"]
