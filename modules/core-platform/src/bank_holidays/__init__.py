"""Bank holidays package for core-platform.

Provides US federal holiday calculation, idempotent seeding, business-day
service, and REST API endpoints for NACHA batch scheduling.
"""

from __future__ import annotations

__all__ = ["seed", "service", "api", "schemas"]
