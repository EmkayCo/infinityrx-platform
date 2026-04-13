"""Dashboard CRUD and widget data service."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.tables import Dashboard, FilterPreset, UserDashboard


class DashboardService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_dashboards(
        self,
        tenant_id: str,
        role_target: str | None = None,
    ) -> list[Dashboard]:
        """List dashboards for a tenant (tenant-specific + system defaults)."""
        stmt = select(Dashboard).where(
            (Dashboard.tenant_id == tenant_id) | (Dashboard.tenant_id.is_(None))
        )
        if role_target:
            stmt = stmt.where(Dashboard.role_target == role_target)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_dashboard(self, dashboard_id: str, tenant_id: str) -> Dashboard | None:
        """Get a dashboard, enforcing tenant isolation."""
        stmt = (
            select(Dashboard)
            .where(
                Dashboard.id == dashboard_id,
            )
            .where((Dashboard.tenant_id == tenant_id) | (Dashboard.tenant_id.is_(None)))
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_dashboard(
        self,
        tenant_id: str,
        data: dict[str, Any],
    ) -> Dashboard:
        """Create a new dashboard for a tenant."""
        dashboard = Dashboard(
            tenant_id=tenant_id,
            name=data["name"],
            description=data.get("description"),
            role_target=data.get("role_target"),
            layout=data.get("layout", []),
        )
        self._db.add(dashboard)
        await self._db.flush()
        return dashboard

    async def update_dashboard(
        self,
        dashboard_id: str,
        tenant_id: str,
        data: dict[str, Any],
    ) -> Dashboard | None:
        """Update dashboard layout; returns None if not found/authorized."""
        dashboard = await self.get_dashboard(dashboard_id, tenant_id)
        if dashboard is None:
            return None
        if data.get("layout") is not None:
            dashboard.layout = data["layout"]
        if "name" in data:
            dashboard.name = data["name"]
        await self._db.flush()
        return dashboard

    async def get_user_dashboard(
        self, user_id: str, tenant_id: str, dashboard_id: str
    ) -> UserDashboard | None:
        """Get user's customized dashboard layout."""
        stmt = select(UserDashboard).where(
            UserDashboard.user_id == user_id,
            UserDashboard.tenant_id == tenant_id,
            UserDashboard.dashboard_id == dashboard_id,
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def save_user_dashboard(
        self,
        user_id: str,
        tenant_id: str,
        dashboard_id: str,
        custom_layout: list[dict[str, Any]] | None = None,
        pinned_filters: dict[str, Any] | None = None,
    ) -> UserDashboard:
        """Save or update a user's dashboard customization."""
        existing = await self.get_user_dashboard(user_id, tenant_id, dashboard_id)
        if existing:
            if custom_layout is not None:
                existing.custom_layout = custom_layout
            if pinned_filters is not None:
                existing.pinned_filters = pinned_filters
            await self._db.flush()
            return existing

        user_dash = UserDashboard(
            user_id=user_id,
            tenant_id=tenant_id,
            dashboard_id=dashboard_id,
            custom_layout=custom_layout,
            pinned_filters=pinned_filters,
        )
        self._db.add(user_dash)
        await self._db.flush()
        return user_dash

    async def list_filter_presets(
        self, tenant_id: str, user_id: str | None = None
    ) -> list[FilterPreset]:
        """List filter presets for a tenant (shared + user-specific)."""
        stmt = select(FilterPreset).where(FilterPreset.tenant_id == tenant_id)
        if user_id:
            stmt = stmt.where((FilterPreset.user_id == user_id) | (FilterPreset.user_id.is_(None)))
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def save_filter_preset(
        self,
        tenant_id: str,
        user_id: str | None,
        name: str,
        filters: dict[str, Any],
        applies_to: dict[str, Any] | None = None,
    ) -> FilterPreset:
        """Save a filter preset."""
        preset = FilterPreset(
            tenant_id=tenant_id,
            user_id=user_id,
            name=name,
            filters=filters,
            applies_to=applies_to,
        )
        self._db.add(preset)
        await self._db.flush()
        return preset

    async def delete_filter_preset(self, preset_id: str, tenant_id: str, user_id: str) -> bool:
        """Delete a user's filter preset."""
        stmt = select(FilterPreset).where(
            FilterPreset.id == preset_id,
            FilterPreset.tenant_id == tenant_id,
            FilterPreset.user_id == user_id,
        )
        result = await self._db.execute(stmt)
        preset = result.scalar_one_or_none()
        if preset is None:
            return False
        await self._db.delete(preset)
        await self._db.flush()
        return True
