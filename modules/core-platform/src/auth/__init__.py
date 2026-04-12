"""core-platform auth module.

Exports ``auth_api_router`` — an APIRouter aggregator to be mounted at
``/api/v1`` by the application composition layer. Also exports
``configure_core_auth`` which wires the shared auth dependencies (user
loader + revoked-token repo) using this module's ORM models.

Import convention: tests add ``modules/core-platform`` to ``sys.path`` so
submodules are importable as ``src.auth.*``. Relative imports are used
internally so the package is relocatable.
"""

from src.auth.api import auth_api_router
from src.auth.wiring import build_user_loader, configure_core_auth

__all__ = ["auth_api_router", "build_user_loader", "configure_core_auth"]
